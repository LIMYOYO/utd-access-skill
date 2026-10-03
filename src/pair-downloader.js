import {DOWNLOAD_ACCESS,parseInformsDoi,libraryLink,detailViewerLink} from './download-policy.js';
import {inspectOrAct} from './download-page.js';
const KEY='parallelPairTask',ALARM='parallelPairDeadline';
export function installPairDownloader(api,{singleBusy=()=>false}={}) {
 let state=null,running=false,writes=Promise.resolve();
 const listeners=new Set(),downloads=new Set(),checks=new Set();
 const alarmName=batch=>ALARM+':'+batch;
 const save=()=>{const snapshot=structuredClone(state);writes=writes.then(async()=>{await api.storage.local.set({[KEY]:snapshot});for(const f of listeners)f(structuredClone(snapshot));});return writes;};
 const ready=(async()=>{state=(await api.storage.local.get(KEY))[KEY]||null;if(state?.phase==='running'){state.phase='needs_attention';state.message='双篇实验已中断，请检查已有文件；不会自动重下。';await save();}})();
 const belongs=batch=>running && state?.request_id===batch;
 async function stop(reason,batch=state?.request_id) {
  if(!belongs(batch))return;
  running=false;state.phase='needs_attention';state.message=reason;await save();await api.alarms.clear(alarmName(batch));
 }
 async function step(paper,action,batch) {
  while(belongs(batch) && Date.now()<state.deadline) {
   const tab=await api.tabs.get(paper.tabId);if(!belongs(batch))throw Error('任务已暂停');
   const origin=new URL(tab.url||'about:blank').origin;
   if(tab.status==='loading' || (tab.pendingUrl && tab.pendingUrl!==tab.url)) {await new Promise(r=>setTimeout(r,750));continue;}
   if(['https://pubsonline.informs.org','https://research.ebsco.com'].includes(origin)) {
    let response;
    try {response=await api.scripting.executeScript({target:{tabId:paper.tabId},func:inspectOrAct,args:[action,{doi:paper.doi,title:paper.title}]});}
    catch(error) {
     if(!['publisher','viewer','dialog-ready'].includes(action))throw error;
     const current=await api.tabs.get(paper.tabId);
     if(current.status!=='loading' && current.url===tab.url && !current.pendingUrl)throw error;
     await new Promise(r=>setTimeout(r,750));continue;
    }
    const result=response[0]?.result;if(result?.error)throw Error(result.error);
    if(result?.navigate) {
     if(action!=='viewer' || !belongs(batch) || !detailViewerLink(result.navigate,tab.url))throw Error('EBSCO 阅读页入口不可信');
     await api.tabs.update(paper.tabId,{url:result.navigate,active:false});continue;
    }
    if(result && !result.waiting){if(!belongs(batch))throw Error('任务已暂停');return result;}
   } else if(!['null','https://libkey.io','https://openurl.ebsco.com'].includes(origin))throw Error('双篇实验遇到登录或其他来源，请检查保留页面。');
   await new Promise(r=>setTimeout(r,750));
  }
  throw Error('双篇实验超时或已暂停');
 }
 async function runPaper(paper,batch) {
  const tab=await api.tabs.create({url:'https://pubsonline.informs.org/doi/'+paper.doi,active:false});paper.tabId=tab.id;
  if(!belongs(batch))return;
  const pub=await step(paper,'publisher',batch);if(!libraryLink(pub.href))throw Error('无可信多大全文入口');paper.title=pub.title;paper.phase='viewer';await save();
  if(!belongs(batch))return;await api.tabs.update(paper.tabId,{url:pub.href,active:false});
  await step(paper,'viewer',batch);await step(paper,'open-dialog',batch);await step(paper,'dialog-ready',batch);
  paper.armedAt=Date.now();paper.phase='waiting_download';await save();
  await step(paper,'click-download',batch);
 }
 async function checkDownload(id,batch) {
  const [item]=await api.downloads.search({id});if(!belongs(batch) || !item)return;
  if(item.state==='interrupted' || item.exists===false)return stop('一个候选下载中断',batch);
  if(item.state!=='complete' || state.candidates.some(c=>c.download_id===id))return;
  if(item.mime!=='application/pdf' || !item.filename?.toLowerCase().endsWith('.pdf'))return stop('候选不是 PDF',batch);
  state.candidates.push({download_id:id,path:item.filename});state.message='候选文件已完成，正在按正文 DOI 分配和核验。';await save();
 }
 // Register checks synchronously so seal observes every already-started event.
 function trackCheck(batch,work) {
  const entry={batch,promise:null};checks.add(entry);
  entry.promise=Promise.resolve().then(()=>{if(belongs(batch) && !state.sealed)return work();})
   .catch(error=>stop(String(error.message),batch)).finally(()=>checks.delete(entry));
 }
 api.downloads.onCreated.addListener(item=>{
  if(!running || state.sealed)return;
  const batch=state.request_id;
  trackCheck(batch,async()=>{
   const armed=state.papers.map(p=>p.armedAt).filter(Number.isFinite);
   if(!armed.length)return;
   try {if(new URL(item.url).origin!=='https://research.ebsco.com')return;}catch{return;}
   const time=Date.parse(item.startTime);if(!(time>=Math.min(...armed) && time<=state.deadline))return;
   downloads.add(item.id);if(downloads.size>2)return stop('候选下载超过两份，停止自动匹配。',batch);
   await checkDownload(item.id,batch);
  });
 });
 api.downloads.onChanged.addListener(delta=>{
  if(running && !state.sealed && downloads.has(delta.id)){
   const batch=state.request_id;trackCheck(batch,()=>checkDownload(delta.id,batch));
  }
 });
 api.alarms.onAlarm.addListener(alarm=>{if(running && alarm.name===alarmName(state.request_id))void stop('双篇实验超时，请检查已下载文件。',state.request_id);});
 return {
  busy:()=>running,
  subscribe:f=>listeners.add(f),
  status:async()=>{await ready;return structuredClone(state);},
  start:async(batch,papers)=>{
   await ready;if(running || singleBusy())throw Error('已有任务进行中');
   if(!Array.isArray(papers)||papers.length!==2)throw Error('双篇实验只接受两篇');
   const normalized=papers.map(p=>({...p,doi:parseInformsDoi(p.doi),phase:'publisher'}));
   if(new Set(normalized.map(p=>p.doi)).size!==2 || new Set(normalized.map(p=>p.request_id)).size!==2)throw Error('论文或任务编号重复');
   running=true;state={request_id:batch,phase:'running',sealed:false,papers:normalized,candidates:[],startedAt:Date.now(),deadline:Date.now()+150000,message:'双篇并行实验进行中'};downloads.clear();
   try {
    if(!await api.permissions.contains(DOWNLOAD_ACCESS))throw Error('未授权论文网站');
    if(!belongs(batch))return;await save();if(!belongs(batch))return;await api.alarms.create(alarmName(batch),{when:state.deadline});
    if(!belongs(batch))return;
    void Promise.all(normalized.map(p=>runPaper(p,batch))).catch(error=>stop(String(error.message),batch));
   }catch(error){await stop(String(error.message),batch);throw error;}
  },
  stop:async batch=>{await ready;if(state?.request_id===batch)await stop('双篇任务已暂停，已开始的下载保留。',batch);},
  seal:async batch=>{
   await ready;
   while(true) {
    if(!belongs(batch))throw Error('批次已暂停或已替换');
    const pending=[...checks].filter(entry=>entry.batch===batch);
    if(!pending.length)break;
    await Promise.all(pending.map(entry=>entry.promise));
   }
   if(downloads.size!==2 || state.candidates.length!==2 || state.candidates.some(c=>!downloads.has(c.download_id)))throw Error('候选池必须恰好包含两个完成的下载');
   const ids=state.candidates.map(c=>c.download_id);
   state.sealed=true;await save();
   if(!belongs(batch) || !state.sealed)throw Error('批次已暂停或已替换');
   return ids;
  },
  applyValidation:async(batch,result)=>{
   await ready;if(state?.request_id!==batch)return false;
   if(result.status==='downloaded_fulltext' && (!running || !state.sealed || result.results?.length!==2 || state.papers.some(p=>!result.results.some(r=>r.request_id===p.request_id&&['verified_fulltext','downloaded_fulltext'].includes(r.status)))))return false;
   if(result.status==='verified_fulltext' && (!running || !state.sealed || result.results?.length!==2 || state.papers.some(p=>!result.results.some(r=>r.request_id===p.request_id&&r.status==='verified_fulltext'))))return false;
   running=false;state.phase=result.status;state.results=result.results;state.message=result.status==='verified_fulltext'?'两篇正文与 DOI 均已核验通过。':result.status==='downloaded_fulltext'?'两篇正文已下载；有论文身份待核对。':'双篇实验需处理：'+result.reason;await save();await api.alarms.clear(alarmName(batch));return true;
  }
 };
}
