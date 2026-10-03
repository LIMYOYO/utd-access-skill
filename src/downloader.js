import { DOWNLOAD_ACCESS, parseInformsDoi, libraryLink, detailViewerLink, matchesDownload, candidateDownload, downloadOutcome } from './download-policy.js';
import { inspectOrAct } from './download-page.js';

const KEY = 'singlePaperTask';
const ALARM = 'singlePaperDeadline';
const active = task => task && ['publisher','viewer','waiting_download'].includes(task.phase);

export function installDownloader(api, {externalBusy=()=>false}={}) {
  let task, busy = false, generation = 0, pendingStart = null;
  let writes = Promise.resolve();
  const listeners = new Set();
  const save = () => {
    const snapshot = {...task};
    writes = writes.then(async () => {
      await api.storage.local.set({[KEY]:snapshot});
      for (const listener of listeners) { try { listener({...snapshot}); } catch (error) { console.error(error); } }
    });
    return writes;
  };
  const stop = async (message, owner = task?.id) => {
    if (!task || task.id !== owner) return;
    task = {...task,phase:'stopped',message};
    await save();
    if (task.id === owner) await api.alarms.clear(ALARM);
  };
  const ready = (async () => {
    task = (await api.storage.local.get(KEY))[KEY];
    if (active(task)) await stop('后台进程已重启，任务已暂停。请先检查原页面及下载记录，勿直接重复下载。');
  })();
  async function step(action) {
    while (active(task) && Date.now() < task.deadline) {
      const tab = await api.tabs.get(task.tabId);
      if (!active(task)) throw Error('任务已暂停。');
      if (tab.status === 'loading' || (tab.pendingUrl && tab.pendingUrl !== tab.url)) {
        await new Promise(resolve => setTimeout(resolve,750));
        continue;
      }
      const origin = new URL(tab.url || 'about:blank').origin;
      if (origin === 'https://pubsonline.informs.org' || origin === 'https://research.ebsco.com') {
        let result;
        try {
          [{result}] = await api.scripting.executeScript({target:{tabId:task.tabId},func:inspectOrAct,args:[action,{doi:task.doi,title:task.title}]});
        } catch (error) {
          // Retry only read-only inspections when a fresh tab snapshot proves navigation.
          // A failed click may already have acted, so never replay it automatically.
          if (!['publisher','viewer','dialog-ready'].includes(action)) throw error;
          const current = await api.tabs.get(task.tabId);
          if (current.status !== 'loading' && current.url === tab.url && !current.pendingUrl) throw error;
          await new Promise(resolve => setTimeout(resolve,750));
          continue;
        }
        if (result?.error) throw Error(result.error);
        if (result?.navigate) {
          if (action !== 'viewer' || !active(task) || !detailViewerLink(result.navigate,tab.url)) throw Error('EBSCO 阅读页入口不可信。');
          await api.tabs.update(task.tabId,{url:result.navigate,active:false});
          continue;
        }
        if (result && !result.waiting) {
          if (!active(task) && !(action === 'click-download' && ['downloaded_unverified','verified_fulltext','downloaded_fulltext'].includes(task.phase))) throw Error('任务已暂停。');
          return result;
        }
      } else if (origin !== 'null' && origin !== 'https://libkey.io' && !(task.phase === 'viewer' && origin === 'https://openurl.ebsco.com')) {
        throw Error('页面需要登录或进入其他来源。已保留后台标签页，请检查后继续。');
      }
      await new Promise(resolve => setTimeout(resolve,750));
    }
    throw Error('等待超时或任务已暂停；请检查保留的页面。');
  }
  async function run() {
    try {
      const publisher = await step('publisher');
      if (!libraryLink(publisher.href)) throw Error('未找到可信的多大 LibKey 全文入口。');
      task.title = publisher.title; task.phase = 'viewer'; await save();
      if (!active(task)) throw Error('任务已暂停。');
      await api.tabs.update(task.tabId,{url:publisher.href,active:false});
      await step('viewer'); await step('open-dialog'); await step('dialog-ready');
      task.viewerUrl = (await api.tabs.get(task.tabId)).url;
      if (!active(task)) throw Error('任务已暂停。');
      task.phase = 'waiting_download'; task.armedAt = Date.now();
      task.message = '已确认论文，正在等待下载完成；请勿关闭任务标签页。'; await save();
      await step('click-download');
    } catch (error) { await stop(error.message || '下载流程失败。'); }
    finally { busy = false; }
  }
  async function check(item, owner) {
    if (!task || task.id !== owner || task.phase !== 'waiting_download') return;
    task.downloadId = item.id;
    task.phase = downloadOutcome(item);
    task.filename = item.filename || '';
    task.message = task.phase === 'downloaded_unverified' ? (task.association === 'candidate_no_referrer' ? '候选 PDF 已下载，但浏览器未提供来源页面。必须由 Codex 核对 DOI 和正文后才能算成功。' : '文件已下载，尚未校验正文。请让 Codex 校验以下文件。') :
      task.phase === 'stopped' ? '下载中断、文件不存在或不是 PDF。' : '下载进行中，请勿关闭任务标签页。';
    await save();
    if (task.id === owner && task.phase !== 'waiting_download') await api.alarms.clear(ALARM);
  }
  api.downloads.onCreated.addListener(item => {
    void ready.then(async () => {
      if (!task || !['waiting_download','downloaded_unverified'].includes(task.phase) || !(matchesDownload({...task,phase:'waiting_download'},item) || candidateDownload({...task,phase:'waiting_download'},item))) return;
      const owner = task.id;
      try {
        if (task.downloadId != null && task.downloadId !== item.id) return await stop('检测到多个候选下载，停止自动判断；请人工核对。',owner);
        if (task.phase !== 'waiting_download') return;
        task.association = matchesDownload({...task,phase:'waiting_download'},item) ? 'viewer_referrer' : 'candidate_no_referrer';
        task.downloadId = item.id; await save();
        if (task.id !== owner || task.phase !== 'waiting_download') return;
        const [current] = await api.downloads.search({id:item.id});
        if (current) await check(current,owner);
      } catch (error) { await stop(`下载记录检查失败：${error.message}`,owner); }
    }).catch(error => console.error('UTD Paper Access storage error:',error.message));
  });
  api.downloads.onChanged.addListener(delta => {
    void ready.then(async () => {
      if (task?.phase !== 'waiting_download' || task.downloadId !== delta.id) return;
      const owner = task.id;
      try {
        const [item] = await api.downloads.search({id:delta.id});
        if (item) await check(item,owner);
      } catch (error) { await stop(`下载状态检查失败：${error.message}`,owner); }
    }).catch(error => console.error('UTD Paper Access storage error:',error.message));
  });
  api.alarms.onAlarm.addListener(alarm => {
    if (alarm.name === ALARM) void ready.then(() => active(task) && stop('任务超时。未确认下载完成，请检查原页面和下载记录；不要盲目重试。'));
  });
  async function startTask(input, requestId) {
    await ready;
    if (requestId && task?.request_id === requestId) return {...task};
      if (externalBusy() || busy || active(task) || (task?.request_id && task.phase === 'downloaded_unverified')) throw Error('已有任务进行中，请先等待或暂停。');
      const doi = parseInformsDoi(input);
      busy = true;
      const request = ++generation;
      pendingStart = {request,requestId};
      try {
        if (!await api.permissions.contains(DOWNLOAD_ACCESS)) throw Error('请先允许下载及论文网站权限。');
        if (request !== generation) throw Error('启动已取消。');
        task = {id:request,request_id:requestId,doi,phase:'publisher',startedAt:Date.now(),deadline:Date.now()+120000,message:'正在定位多大全文入口。'};
        const tab = await api.tabs.create({url:`https://pubsonline.informs.org/doi/${doi}`,active:false});
        task.tabId = tab.id;
        if (request !== generation || !active(task)) throw Error('启动已取消；保留任务标签页。');
        await save(); await api.alarms.create(ALARM,{when:task.deadline});
      } catch (error) { busy=false; await stop(error.message,request); throw error; }
      finally { if (pendingStart?.request === request) pendingStart = null; }
      void run(); return task;
  }
  const controller = {
    start:startTask,
    isBusy:()=>busy || active(task) || Boolean(task?.request_id && task.phase === 'downloaded_unverified'),
    status:async () => { await ready; return task ? {...task} : null; },
    stop:async requestId => {
      await ready;
      if (requestId && task?.request_id !== requestId) return false;
      generation++; await stop('任务已暂停，已开始的下载保留。'); return true;
    },
    disconnect:async requestId => {
      const cancelledStart = pendingStart && (!requestId || pendingStart.requestId === requestId);
      if (cancelledStart) generation++;
      await ready;
      if (requestId && task?.request_id !== requestId) return Boolean(cancelledStart);
      generation++;
      if (active(task)) await stop('本地连接断开，任务已暂停；已下载候选保留，未自动重新下载。');
      return true;
    },
    subscribe:listener => { listeners.add(listener); return () => listeners.delete(listener); },
    applyValidation:async (requestId,result) => {
      await ready;
      if (task?.request_id !== requestId || task.phase !== 'downloaded_unverified') return false;
      if (!['verified_fulltext','downloaded_fulltext','needs_attention','failed','cancelled'].includes(result.status)) return false;
      task = {...task,phase:result.status,message:result.status === 'verified_fulltext' ? '正文与 DOI 已由本地工具核验通过。' : result.status === 'downloaded_fulltext' ? '正文已下载；身份待核对，允许继续分析。' : result.reason};
      await save(); return true;
    }
  };
  api.runtime.onMessage.addListener((message,sender,respond) => {
    if (sender.id !== api.runtime.id || sender.tab || sender.url !== api.runtime.getURL('src/popup.html')) return;
    if (!['paper-start','paper-status','paper-stop','paper-diagnose'].includes(message?.type)) return;
    void ready.then(async () => {
      if (message.type === 'paper-status') return task || null;
      if (message.type === 'paper-diagnose') {
        const snapshot = {...task};
        if (!Number.isFinite(snapshot.armedAt) || !Number.isFinite(snapshot.deadline)) throw Error('本次任务尚未发起下载，无需检查记录。');
        const items = await api.downloads.search({
          startedAfter:new Date(snapshot.armedAt-1).toISOString(),
          startedBefore:new Date(snapshot.deadline+1).toISOString(),
          filenameRegex:'EBSCO-FullText-.*\\.pdf$',limit:10,orderBy:['-startTime']
        });
        const origin = value => { try { return new URL(value).origin; } catch { return ''; } };
        // Diagnostics never bind a download or change its verification state.
        return {id:snapshot.id,doi:snapshot.doi,phase:snapshot.phase,diagnostics:items.map(item => ({
          id:item.id,state:item.state,mime:item.mime,
          referrerPresent:Boolean(item.referrer),referrerOrigin:origin(item.referrer),
          downloadOrigin:origin(item.url),
          pathMatches:matchesDownload({...snapshot,phase:'waiting_download'},item),
          startOffsetMs:Date.parse(item.startTime)-snapshot.armedAt
        }))};
      }
      if (message.type === 'paper-stop') { generation++; await stop('用户已暂停。原标签页和已开始的下载保留。'); return task; }
      return startTask(message.doi);
    }).then(result => respond({ok:true,task:result})).catch(error => respond({ok:false,error:error.message}));
    return true;
  });
  return controller;
}
