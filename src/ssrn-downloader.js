import {SSRN_ACCESS,parseSsrnId,ssrnDownloadLink,matchesSsrnDownload} from './ssrn-policy.js';
import {inspectSsrnPage} from './ssrn-page.js';

const KEY='ssrnPaperTask',ALARM='ssrnPaperDeadline';
const ACTIVE=['publisher','waiting_download','downloaded_unverified'];
export function installSsrnDownloader(api,{externalBusy=()=>false,pause=ms=>new Promise(r=>setTimeout(r,ms)),now=()=>Date.now()}={}) {
  let task=null,starting=false,pendingStart=null,serial=Promise.resolve();const listeners=new Set(),pendingDownloads=new Set();
  const locked=fn=>{const next=serial.then(fn);serial=next.catch(()=>{});return next;};
  const ready=api.storage.local.get(KEY).then(async data=>{
    task=data[KEY]||null;
    if(task&&['publisher','waiting_download'].includes(task.phase)){task={...task,phase:'needs_attention',message:'扩展重启，未自动重新下载'};await save();}
  });
  async function save(){await api.storage.local.set({[KEY]:task});for(const fn of listeners)fn(structuredClone(task));}
  async function update(id,patch,expected){return locked(async()=>{if(task?.request_id!==id||(expected&&task.phase!==expected))return false;Object.assign(task,patch);await save();return true;});}
  async function stop(id,reason='SSRN 下载已停止') {
    if(pendingStart?.id===id)pendingStart.cancelled=true;
    return locked(async()=>{await ready;if(task?.request_id!==id||!ACTIVE.includes(task.phase))return false;task.phase='needs_attention';task.message=reason;await api.alarms.clear(ALARM);await save();return true;});
  }
  async function run(id,tabId) {
    try {
      while(task?.request_id===id&&task.phase==='publisher'&&now()<task.deadline) {
        let page;
        try {const replies=await api.scripting.executeScript({target:{tabId},func:inspectSsrnPage,args:[task.ssrn_id]});page=replies[0]?.result;}
        catch {await pause(750);continue;}
        if(task?.request_id!==id||task.phase!=='publisher')return;
        if(page?.status==='attention'){await stop(id,page.reason);return;}
        if(page?.status==='ready') {
          if(!ssrnDownloadLink(page.url,task.ssrn_id)||!Array.isArray(page.authors)||!page.authors.length){await stop(id,'论文下载入口校验失败');return;}
          await update(id,{phase:'waiting_download',title:page.title,authors:page.authors,downloadUrl:page.url,armedAt:now(),message:'已触发正常下载，等待文件完成；若出现验证请人工完成'},'publisher');
          // Cancel and restart cannot reuse this action after an awaited storage write.
          if(task?.request_id!==id||task.phase!=='waiting_download')return;
          const replies=await api.scripting.executeScript({target:{tabId},func:inspectSsrnPage,args:[task.ssrn_id,'click',page.url]});
          if(replies[0]?.result?.status==='attention')await stop(id,replies[0].result.reason);
          return;
        }
        if(page?.reason&&task.message!==page.reason)await update(id,{message:page.reason});
        await pause(750);
      }
      if(task?.request_id===id&&task.phase==='publisher')await stop(id,'SSRN 页面等待超时，请完成验证后重新提交');
    } catch(error){await stop(id,String(error.message).slice(0,500));}
  }
  async function start(input,id) {
    if(starting)throw Error('下载工具正在运行');starting=true;
    const token={id,cancelled:false};pendingStart=token;
    const assertCurrent=()=>{if(token.cancelled)throw Error('启动已取消，未重新下载');};
    try {
      await ready;assertCurrent();const ssrn_id=parseSsrnId(input);
      if(ACTIVE.includes(task?.phase)||externalBusy())throw Error('下载工具正在运行');
      if(!await api.permissions.contains(SSRN_ACCESS))throw Error('请先在扩展中启用 SSRN 网站权限');
      assertCurrent();
      const deadline=now()+240000;
      await locked(async()=>{assertCurrent();task={request_id:id,ssrn_id,doi:'10.2139/ssrn.'+ssrn_id,phase:'publisher',deadline,message:'正在打开 SSRN 论文页面'};await save();});
      assertCurrent();
      await api.alarms.create(ALARM,{when:deadline});
      assertCurrent();
      const tab=await api.tabs.create({url:'https://papers.ssrn.com/sol3/papers.cfm?abstract_id='+ssrn_id,active:false});
      assertCurrent();
      if(task?.request_id===id&&task.phase==='publisher'){await update(id,{tabId:tab.id});void run(id,tab.id);}
      return structuredClone(task);
    } catch(error){if(task?.request_id===id)await stop(id,error.message);throw error;}
    finally{starting=false;if(pendingStart===token)pendingStart=null;}
  }
  async function capture(item) {
    await ready;
    let matched=false;
    await locked(async()=>{
      if(!task||!matchesSsrnDownload(task,item))return;
      if(task.downloadId!==undefined&&task.downloadId!==item.id){
        task.phase='needs_attention';task.message='多个匹配下载，需人工核对';await api.alarms.clear(ALARM);await save();return;
      }
      task.downloadId=item.id;matched=true;await save();
    });
    if(matched)await check(item.id);
  }
  async function check(downloadId) {
    const id=task?.request_id;
    if(task?.phase!=='waiting_download'||task.downloadId!==downloadId)return;
    const items=await api.downloads.search({id:downloadId}),item=items[0];
    if(task?.request_id!==id||task.phase!=='waiting_download'||task.downloadId!==downloadId)return;
    if(!item||item.state==='interrupted'||item.exists===false){await stop(id,'SSRN 文件下载失败或文件已消失');return;}
    if(item.state!=='complete')return;
    if(item.mime!=='application/pdf'||!/\.pdf$/i.test(item.filename||'')){await stop(id,'下载结果不是 PDF');return;}
    await update(id,{phase:'downloaded_unverified',filename:item.filename,message:'文件下载完成，等待本地正文校验'},'waiting_download');await api.alarms.clear(ALARM);
  }
  api.downloads.onCreated.addListener(item=>{
    // Register synchronously so a nearby native success cannot outrun this event.
    const pending=ready.then(()=>{const id=task?.request_id;return capture(item).catch(error=>stop(id,error.message));});
    pendingDownloads.add(pending);pending.then(()=>pendingDownloads.delete(pending),()=>pendingDownloads.delete(pending));
  });
  api.downloads.onChanged.addListener(delta=>{void ready.then(()=>{const id=task?.request_id;return check(delta.id).catch(error=>stop(id,error.message));});});
  api.alarms.onAlarm.addListener(alarm=>{if(alarm.name===ALARM)void ready.then(()=>stop(task?.request_id,'SSRN 下载超时，请检查页面验证或下载状态'));});
  return {start,stop,disconnect:async id=>{
    if(pendingStart?.id===id)pendingStart.cancelled=true;
    await ready;
    if(task?.request_id===id&&['publisher','waiting_download'].includes(task.phase))return stop(id,'本地连接断开，未重新下载');
    return false;
  },isBusy:()=>starting||ACTIVE.includes(task?.phase),status:async()=>{await ready;return structuredClone(task);},subscribe:fn=>listeners.add(fn),applyValidation:async(id,result)=>{
    if(!['verified_fulltext','downloaded_fulltext','needs_attention','failed','cancelled'].includes(result.status))return false;
    for(;;) {
      if((await Promise.allSettled([...pendingDownloads])).some(x=>x.status==='rejected'))return false;
      const applied=await locked(async()=>{
        if(pendingDownloads.size)return null;
        if(task?.request_id!==id||task.phase!=='downloaded_unverified')return false;
        task.phase=result.status;task.message=result.reason;await save();return true;
      });
      if(applied!==null)return applied;
    }
  }};
}
