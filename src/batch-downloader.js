import {DOWNLOAD_ACCESS,parseInformsDoi,libraryLink,detailViewerLink} from './download-policy.js';
import {inspectOrAct} from './download-page.js';
const KEY='parallelBatchTask',PREFIX='parallelBatchDeadline:';
const terminal=p=>['verified_fulltext','downloaded_fulltext','needs_attention','failed','cancelled'].includes(p.phase);
export function installBatchDownloader(api,{externalBusy=()=>false}={}) {
 let state=null,running=false,writes=Promise.resolve();
 const authOwners=new Set(),authQueue=[];
 const listeners=new Set(),working=new Set(),downloads=new Set(),checks=new Set();
 const belongs=batch=>running&&state?.request_id===batch;
 const alarm=(batch,paper)=>PREFIX+batch+':'+paper.request_id;
 const save=()=>{const snapshot=structuredClone(state);writes=writes.then(async()=>{await api.storage.local.set({[KEY]:snapshot});for(const f of listeners){try{f(structuredClone(snapshot));}catch(error){console.error(error);}}});return writes;};
 const ready=(async()=>{state=(await api.storage.local.get(KEY))[KEY]||null;if(state?.phase==='running'){state.phase='needs_attention';state.message='并发任务中断，请检查保留文件；不会自动重下。';for(const p of state.papers)if(!terminal(p)){p.phase='needs_attention';p.reason='worker_restarted';}await save();}})();
 function releaseAuth(token) {
  if(!authOwners.delete(token))return;
  while(authQueue.length&&authOwners.size<2){
   const next=authQueue.shift();
   if(!active(next.paper,next.batch)){next.reject(Error('任务已结束'));continue;}
   const owner={batch:next.batch,paper:next.paper};authOwners.add(owner);next.resolve(owner);
  }
 }
 function acquireAuth(paper,batch){
  if(!active(paper,batch))return Promise.reject(Error('任务已结束'));
  if(authOwners.size<2){const owner={batch,paper};authOwners.add(owner);return Promise.resolve(owner);}
  return new Promise((resolve,reject)=>authQueue.push({paper,batch,resolve,reject}));
 }
 function cancelAuth(paper,batch){
  for(let i=authQueue.length-1;i>=0;i--)if(authQueue[i].batch===batch&&authQueue[i].paper===paper){authQueue.splice(i,1)[0].reject(Error('任务已结束'));}
  for(const owner of [...authOwners])if(owner.batch===batch&&owner.paper===paper)releaseAuth(owner);
 }
 async function stop(reason,batch=state?.request_id) {
  if(!belongs(batch))return;
  running=false;state.phase='needs_attention';state.message=reason;
  const papers=state.papers;for(const p of papers)if(!terminal(p)){p.phase='needs_attention';p.reason=reason;}
  working.clear();for(const entry of authQueue.splice(0))entry.reject(Error('任务已暂停'));authOwners.clear();await save();await Promise.all(papers.map(p=>api.alarms.clear(alarm(batch,p))));
 }
 async function settle(paper,status,reason,batch) {
  if(!belongs(batch)||terminal(paper))return false;
  paper.phase=status;paper.reason=reason;working.delete(paper.request_id);cancelAuth(paper,batch);
  state.message=state.papers.filter(terminal).length+'/'+state.papers.length+' 篇已完成处理';
  await save();await api.alarms.clear(alarm(batch,paper));if(belongs(batch))pump(batch);return true;
 }
 const active=(paper,batch)=>belongs(batch)&&!terminal(paper);
 async function step(paper,action,batch) {
  while(active(paper,batch)&&Date.now()<paper.deadline) {
   const tab=await api.tabs.get(paper.tabId);if(!active(paper,batch))throw Error('任务已结束');
   if(tab.status==='loading'||(tab.pendingUrl&&tab.pendingUrl!==tab.url)){await new Promise(r=>setTimeout(r,750));continue;}
   const origin=new URL(tab.url||'about:blank').origin;
   if(['https://pubsonline.informs.org','https://research.ebsco.com'].includes(origin)) {
    let response;
    try{response=await api.scripting.executeScript({target:{tabId:paper.tabId},func:inspectOrAct,args:[action,{doi:paper.doi,title:paper.title}]});}
    catch(error){
     if(!['publisher','viewer','dialog-ready'].includes(action))throw error;
     const current=await api.tabs.get(paper.tabId);
     if(current.status!=='loading'&&current.url===tab.url&&!current.pendingUrl)throw error;
     await new Promise(r=>setTimeout(r,750));continue;
    }
    const result=response[0]?.result;if(result?.error)throw Error(result.error);
    if(result?.navigate){
     if(action!=='viewer'||!active(paper,batch)||!detailViewerLink(result.navigate,tab.url))throw Error('EBSCO 阅读页入口不可信');
     await api.tabs.update(paper.tabId,{url:result.navigate,active:false});continue;
    }
    if(result&&!result.waiting){if(!active(paper,batch))throw Error('任务已结束');return result;}
   }else if(!['null','https://libkey.io','https://openurl.ebsco.com'].includes(origin))throw Error('此篇需要登录或进入其他全文来源');
   await new Promise(r=>setTimeout(r,750));
  }
  throw Error('此篇超时或已结束');
 }
 async function runPaper(paper,batch) {
  try{
   const tab=await api.tabs.create({url:'https://pubsonline.informs.org/doi/'+paper.doi,active:false});if(!active(paper,batch))return;
   paper.tabId=tab.id;await save();if(!active(paper,batch))return;
   await api.alarms.create(alarm(batch,paper),{when:paper.deadline});
   const pub=await step(paper,'publisher',batch);if(!libraryLink(pub.href))throw Error('无可信多大全文入口');
   paper.title=pub.title;paper.phase='waiting_access';await save();if(!active(paper,batch))return;
   const owner=await acquireAuth(paper,batch);
   try {
    if(!active(paper,batch))return;
    paper.phase='viewer';paper.authStartedAt=Date.now();await save();if(!active(paper,batch))return;
    await api.tabs.update(paper.tabId,{url:pub.href,active:false});
    await step(paper,'viewer',batch);
    paper.authFinishedAt=Date.now();
   }finally{releaseAuth(owner);}
   await step(paper,'open-dialog',batch);await step(paper,'dialog-ready',batch);
   if(!active(paper,batch))return;
   paper.armedAt=Date.now();paper.phase='waiting_download';await save();await step(paper,'click-download',batch);
  }catch(error){await settle(paper,'needs_attention',String(error.message),batch);}
 }
 function pump(batch) {
  if(!belongs(batch))return;
  for(const p of state.papers){
   if(working.size>=state.concurrency)break;
   if(p.phase!=='queued')continue;
   working.add(p.request_id);p.phase='publisher';p.startedAt=Date.now();p.deadline=Date.now()+150000;void runPaper(p,batch);
  }
 }
 async function check(id,batch){
  const [item]=await api.downloads.search({id});if(!belongs(batch)||!item)return;
  if(item.state==='interrupted'||item.exists===false)return stop('候选下载中断，无法唯一确定受影响论文',batch);
  if(item.state!=='complete'||state.candidates.some(c=>c.download_id===id))return;
  if(item.mime!=='application/pdf'||!item.filename?.toLowerCase().endsWith('.pdf'))return stop('候选不是PDF，需检查文件归属',batch);
  state.candidates.push({download_id:id,path:item.filename});await save();
 }
 function track(batch,work){
  const entry={batch,promise:null};checks.add(entry);
  entry.promise=Promise.resolve().then(()=>{if(belongs(batch)&&!state.sealed)return work();}).catch(e=>stop(String(e.message),batch)).finally(()=>checks.delete(entry));
 }
 api.downloads.onCreated.addListener(item=>{
  if(!running||state.sealed)return;const batch=state.request_id;
  track(batch,async()=>{
   const armed=state.papers.map(p=>p.armedAt).filter(Number.isFinite);if(!armed.length)return;
   try{if(new URL(item.url).origin!=='https://research.ebsco.com')return;}catch{return;}
   if(!(Date.parse(item.startTime)>=Math.min(...armed)&&Date.parse(item.startTime)<=state.deadline))return;
   downloads.add(item.id);if(downloads.size>state.papers.length)return stop('候选文件超过论文数，停止自动匹配',batch);
   await check(item.id,batch);
  });
 });
 api.downloads.onChanged.addListener(delta=>{if(running&&!state.sealed&&downloads.has(delta.id)){const batch=state.request_id;track(batch,()=>check(delta.id,batch));}});
 api.alarms.onAlarm.addListener(event=>{
  if(!running)return;const batch=state.request_id,p=state.papers.find(p=>alarm(batch,p)===event.name);
  if(p)void settle(p,'needs_attention','此篇下载或核验超时',batch);
 });
 return {
  busy:()=>running,subscribe:f=>listeners.add(f),status:async()=>{await ready;return structuredClone(state);},
  start:async(batch,papers,concurrency)=>{
   await ready;if(running||externalBusy())throw Error('已有任务进行中');
   if(!Array.isArray(papers)||papers.length<1||papers.length>10||!Number.isInteger(concurrency)||concurrency<1||concurrency>10)throw Error('最多10篇，并发数须为1至10');
   const normalized=papers.map(p=>({...p,doi:parseInformsDoi(p.doi),phase:'queued'}));
   if(new Set(normalized.map(p=>p.doi)).size!==papers.length||new Set(normalized.map(p=>p.request_id)).size!==papers.length)throw Error('论文或任务编号重复');
   running=true;state={request_id:batch,phase:'running',papers:normalized,concurrency,candidates:[],sealed:false,startedAt:Date.now(),deadline:Date.now()+Math.ceil(papers.length/concurrency)*150000+30000,message:'并发论文下载进行中'};working.clear();downloads.clear();
   try{if(!await api.permissions.contains(DOWNLOAD_ACCESS))throw Error('未授权论文网站');if(!belongs(batch))return;await save();if(belongs(batch))pump(batch);}
   catch(error){await stop(String(error.message),batch);throw error;}
  },
  stop:async batch=>{await ready;await stop('并发任务已暂停，已下载文件保留',batch);},
  applyPaperResult:async(batch,id,result)=>{
   await ready;if(!belongs(batch)||!['verified_fulltext','downloaded_fulltext','needs_attention','failed','cancelled'].includes(result.status))return false;
   const p=state.papers.find(p=>p.request_id===id);if(!p||p.phase==='queued')return false;
   return settle(p,result.status,result.reason,batch);
  },
  seal:async batch=>{
   await ready;while(true){if(!belongs(batch))throw Error('任务已暂停或替换');const pending=[...checks].filter(c=>c.batch===batch);if(!pending.length)break;await Promise.all(pending.map(c=>c.promise));}
   if(state.papers.some(p=>!terminal(p))||state.candidates.length!==downloads.size)throw Error('还有论文或下载未完成');
   const ids=state.candidates.map(c=>c.download_id);state.sealed=true;await save();if(!belongs(batch))throw Error('任务已暂停或替换');return ids;
  },
  finish:async(batch,result)=>{
   await ready;if(state?.request_id!==batch)return false;
   if(result.status==='downloaded_fulltext'&&(!belongs(batch)||!state.sealed||state.papers.some(p=>!['verified_fulltext','downloaded_fulltext'].includes(p.phase))))return false;
   if(result.status==='verified_fulltext'&&(!belongs(batch)||!state.sealed||state.papers.some(p=>p.phase!=='verified_fulltext')))return false;
   for(const resultPaper of result.results||[]){
    const paper=state.papers.find(p=>p.request_id===resultPaper.request_id);
    if(paper&&paper.phase!=='verified_fulltext'&&['needs_attention','failed','cancelled'].includes(resultPaper.status)){paper.phase=resultPaper.status;paper.reason=resultPaper.reason;}
   }
   running=false;state.phase=result.status;state.results=result.results;state.message=state.papers.filter(p=>['verified_fulltext','downloaded_fulltext'].includes(p.phase)).length+'/'+state.papers.length+' 篇正文已下载；'+state.papers.filter(p=>p.phase==='verified_fulltext').length+' 篇身份通过';await save();return true;
  }
 };
}
