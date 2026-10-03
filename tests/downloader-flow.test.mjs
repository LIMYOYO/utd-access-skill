import test from 'node:test';
import assert from 'node:assert/strict';
import { installDownloader } from '../src/downloader.js';

const event = () => { const handlers=[]; return {addListener:fn=>handlers.push(fn), fire:(...args)=>handlers.forEach(fn=>fn(...args)), handlers}; };
const flush = () => new Promise(resolve=>setImmediate(resolve));
function harness({restored,permission=true,referrer=true,downloadUrl=undefined}={}) {
  const memory={singlePaperTask:restored}, actions=[];
  let current={id:4,url:''}, download;
  const api={
    storage:{local:{get:async()=>structuredClone(memory),set:async data=>Object.assign(memory,structuredClone(data))}},
    permissions:{contains:async()=>permission},
    alarms:{create:async()=>{},clear:async()=>{},onAlarm:event()},
    tabs:{create:async args=>{actions.push(['create',args]);current={id:4,...args};return current;},get:async()=>current,update:async(id,args)=>{actions.push(['update',args]);current={id,url:'https://research.ebsco.com/c/example/viewer/pdf/abc'};return current;}},
    downloads:{onCreated:event(),onChanged:event(),search:async()=>[download]},
    runtime:{id:'test',getURL:path=>'chrome-extension://test/'+path,onMessage:event()},
    scripting:{executeScript:async({args:[action]})=>{
      actions.push([action]);
      if(action==='publisher')return [{result:{title:'A paper',href:'https://libkey.io/libraries/278/articles/123/full-text-file'}}];
      if(action==='click-download') {
        download={id:8,url:downloadUrl,state:'in_progress',referrer:referrer?current.url:'',startTime:new Date(Date.now()+1).toISOString(),mime:'application/pdf',filename:'/tmp/paper.pdf',exists:true};
        api.downloads.onCreated.fire(download);
      }
      return [{result:{done:true}}];
    }}
  };
  const controller=installDownloader(api);
  const send=message=>new Promise(resolve=>api.runtime.onMessage.handlers[0](message,{id:'test',url:api.runtime.getURL('src/popup.html')},resolve));
  return {api,memory,actions,send,controller,complete:()=>{download.state='complete';api.downloads.onChanged.fire({id:8,state:{current:'complete'}});}};
}

test('one background task waits for Chrome completion and remains unverified',async()=>{
  const h=harness();assert.equal((await h.send({type:'paper-start',doi:'10.1287/mnsc.2018.3061'})).ok,true);
  await flush();await flush();
  assert.equal(h.memory.singlePaperTask.phase,'waiting_download');
  assert.equal(h.actions[0][1].active,false);
  assert.equal(h.actions.filter(x=>x[0]==='click-download').length,1);
  h.complete();await flush();
  assert.equal(h.memory.singlePaperTask.phase,'downloaded_unverified');
  assert.equal(h.memory.singlePaperTask.filename,'/tmp/paper.pdf');
  assert.equal(h.actions.filter(x=>x[0]==='update').length,1,'never navigate away after clicking download');
});
test('missing referrer never binds an unrelated download; timeout preserves task tab',async()=>{
  const h=harness({referrer:false});await h.send({type:'paper-start',doi:'10.1287/mnsc.2018.3061'});await flush();await flush();
  h.complete();await flush();assert.equal(h.memory.singlePaperTask.phase,'waiting_download');
  h.api.alarms.onAlarm.fire({name:'singlePaperDeadline'});await flush();assert.equal(h.memory.singlePaperTask.phase,'stopped');
});
test('permission denial creates no tab',async()=>{
  const h=harness({permission:false});assert.equal((await h.send({type:'paper-start',doi:'10.1287/mnsc.2018.3061'})).ok,false);assert.equal(h.actions.length,0);
});
test('concurrent starts cannot create duplicate task tabs',async()=>{
  const h=harness();const replies=await Promise.all([h.send({type:'paper-start',doi:'10.1287/mnsc.2018.3061'}),h.send({type:'paper-start',doi:'10.1287/msom.2019.0800'})]);await flush();
  assert.equal(replies.filter(x=>x.ok).length,1);assert.equal(h.actions.filter(x=>x[0]==='create').length,1);
});
test('worker restart pauses persisted task instead of replaying clicks',async()=>{
  const h=harness({restored:{phase:'waiting_download',tabId:4,doi:'10.1287/foo'}});
  const reply=await h.send({type:'paper-status'});assert.equal(reply.task.phase,'stopped');assert.equal(h.actions.length,0);
});

test('pause during a pending page inspection prevents later navigation',async()=>{
  const h=harness();let finishInspection;
  h.api.scripting.executeScript=()=>new Promise(resolve=>{finishInspection=resolve;});
  await h.send({type:'paper-start',doi:'10.1287/mnsc.2018.3061'});await flush();
  await h.send({type:'paper-stop'});
  finishInspection([{result:{title:'A paper',href:'https://libkey.io/libraries/278/articles/123/full-text-file'}}]);
  await flush();assert.equal(h.memory.singlePaperTask.phase,'stopped');
  assert.equal(h.actions.filter(x=>x[0]==='update').length,0);
});

test('webpage and content-script messages cannot start downloads',()=>{
  const h=harness();let replied=false;
  const listener=h.api.runtime.onMessage.handlers[0];
  assert.equal(listener({type:'paper-start',doi:'10.1287/foo'},{id:'test',tab:{id:1},url:'https://research.ebsco.com/'},()=>{replied=true;}),undefined);
  assert.equal(replied,false);assert.equal(h.actions.length,0);
});

test('pause while permission check is pending cancels startup before creating a tab',async()=>{
  const h=harness();let resolvePermission;
  h.api.permissions.contains=()=>new Promise(resolve=>{resolvePermission=resolve;});
  const pending=h.send({type:'paper-start',doi:'10.1287/mnsc.2018.3061'});await flush();
  await h.send({type:'paper-stop'});resolvePermission(true);
  assert.equal((await pending).ok,false);assert.equal(h.actions.length,0);
});

test('a second matching download invalidates even a just-completed candidate',async()=>{
  const h=harness();await h.send({type:'paper-start',doi:'10.1287/mnsc.2018.3061'});await flush();await flush();
  h.complete();await flush();
  h.api.downloads.onCreated.fire({id:9,startTime:new Date().toISOString(),referrer:'https://research.ebsco.com/c/example/viewer/pdf/abc'});await flush();
  assert.equal(h.memory.singlePaperTask.phase,'stopped');
});

test('an old download query rejection cannot stop a replacement task',async()=>{
  const h=harness();await h.send({type:'paper-start',doi:'10.1287/mnsc.2018.3061'});await flush();await flush();
  let rejectOld;
  const originalSearch=h.api.downloads.search;
  h.api.downloads.search=()=>new Promise((resolve,reject)=>{rejectOld=reject;});
  h.api.downloads.onChanged.fire({id:8});await flush();
  await h.send({type:'paper-stop'});h.api.downloads.search=originalSearch;
  await h.send({type:'paper-start',doi:'10.1287/msom.2019.0800'});await flush();await flush();
  rejectOld(Error('old query failed'));await flush();
  assert.equal(h.memory.singlePaperTask.doi,'10.1287/msom.2019.0800');
  assert.equal(h.memory.singlePaperTask.phase,'waiting_download');
});


test('loading and observed EBSCO redirect pages are waited out without script injection',async()=>{
  const h=harness();const get=h.api.tabs.get;let reads=0;
  h.api.tabs.get=async()=>{
    const tab=await get();
    if(h.memory.singlePaperTask?.phase==='viewer') {
      reads++;
      if(reads===1)return {...tab,status:'loading',url:'https://libkey.io/libraries/278/articles/123/full-text-file'};
      if(reads===2)return {...tab,status:'complete',url:'https://openurl.ebsco.com/c/gsemyh/detailv2'};
    }
    return tab;
  };
  await h.send({type:'paper-start',doi:'10.1287/mnsc.2018.3061'});
  await new Promise(resolve=>setTimeout(resolve,1650));
  assert.equal(h.memory.singlePaperTask.phase,'waiting_download');
  assert.equal(h.actions.filter(x=>x[0]==='click-download').length,1);
});

test('read inspection racing a redirect is retried after observing navigation',async()=>{
  const h=harness();const execute=h.api.scripting.executeScript;const get=h.api.tabs.get;let redirected=false,failed=false;
  h.api.scripting.executeScript=async args=>{
    if(args.args[0]==='viewer'&&!failed){failed=true;redirected=true;throw Error('Cannot access contents of the page');}
    return execute(args);
  };
  h.api.tabs.get=async()=>{
    const tab=await get();
    if(redirected){redirected=false;return {...tab,url:'https://openurl.ebsco.com/c/gsemyh/detailv2',status:'loading'};}
    return tab;
  };
  await h.send({type:'paper-start',doi:'10.1287/mnsc.2018.3061'});
  await new Promise(resolve=>setTimeout(resolve,850));
  assert.equal(h.memory.singlePaperTask.phase,'waiting_download');
});

test('stable page permission failures stop rather than retrying indefinitely',async()=>{
  const h=harness();h.api.scripting.executeScript=async()=>{throw Error('permission denied');};
  await h.send({type:'paper-start',doi:'10.1287/mnsc.2018.3061'});await flush();await flush();
  assert.equal(h.memory.singlePaperTask.phase,'stopped');
  assert.equal(h.memory.singlePaperTask.message,'permission denied');
});


test('diagnostic reads only the task time window and never promotes a candidate',async()=>{
  const h=harness({restored:{id:1,phase:'stopped',armedAt:1000,deadline:121000,viewerUrl:'https://research.ebsco.com/c/test/viewer/pdf/abc'}});
  let query;
  h.api.downloads.search=async q=>{query=q;return [{id:8,state:'complete',mime:'application/pdf',referrer:'https://research.ebsco.com/?secret=hidden',url:'blob:https://research.ebsco.com/opaque-token',startTime:new Date(2000).toISOString()}];};
  const reply=await h.send({type:'paper-diagnose'});
  assert.equal(query.startedAfter,new Date(999).toISOString());assert.equal(query.startedBefore,new Date(121001).toISOString());
  assert.equal(query.filenameRegex,'EBSCO-FullText-.*\\.pdf$');
  assert.equal(reply.task.phase,'stopped');
  assert.equal(reply.task.diagnostics[0].referrerOrigin,'https://research.ebsco.com');
  assert.equal(reply.task.diagnostics[0].pathMatches,false);
  assert.equal(JSON.stringify(reply).includes('secret'),false);assert.equal(JSON.stringify(reply).includes('opaque-token'),false);
});

test('diagnostic without an armed download does not search history',async()=>{
  const h=harness();let searched=false;h.api.downloads.search=async()=>{searched=true;return [];};
  const reply=await h.send({type:'paper-diagnose'});assert.equal(reply.ok,false);assert.equal(searched,false);
});


test('EBSCO without referrer completes only as an explicitly unverified candidate',async()=>{
  const h=harness({referrer:false,downloadUrl:'blob:https://research.ebsco.com/opaque'});
  await h.send({type:'paper-start',doi:'10.1287/mnsc.2018.3061'});await flush();await flush();
  assert.equal(h.memory.singlePaperTask.phase,'waiting_download');
  h.complete();await flush();
  assert.equal(h.memory.singlePaperTask.phase,'downloaded_unverified');
  assert.equal(h.memory.singlePaperTask.association,'candidate_no_referrer');
  assert.match(h.memory.singlePaperTask.message,/候选/);
  h.api.downloads.onCreated.fire({id:9,url:'blob:https://research.ebsco.com/other',referrer:'',startTime:new Date().toISOString()});await flush();
  assert.equal(h.memory.singlePaperTask.phase,'stopped');
});


test('bridge holds single-flight until validation and rejects stale validation',async()=>{
  const h=harness();const id='11111111-1111-4111-8111-111111111111';
  await h.controller.start('10.1287/mnsc.2018.3061',id);await flush();await flush();h.complete();await flush();
  assert.equal((await h.send({type:'paper-start',doi:'10.1287/msom.2019.0800'})).ok,false);
  assert.equal(await h.controller.applyValidation('wrong',{status:'verified_fulltext',reason:''}),false);
  assert.equal(await h.controller.applyValidation(id,{status:'verified_fulltext',reason:''}),true);
  assert.equal((await h.controller.status()).phase,'verified_fulltext');
});

test('detail entry navigates to same-record viewer in background before one download',async()=>{
 const h=harness();const execute=h.api.scripting.executeScript;let current,detailReads=0;
 h.api.tabs.get=async()=>current;
 const create=h.api.tabs.create;h.api.tabs.create=async args=>{current=await create(args);return current;};
 h.api.tabs.update=async(id,args)=>{h.actions.push(['route-update',args]);current={id,url:args.url.startsWith('https://libkey.io')?'https://research.ebsco.com/c/gsemyh/search/details/abc':args.url};return current;};
 h.api.scripting.executeScript=async args=>{
  if(args.args[0]==='viewer' && current.url.includes('/search/details/')){detailReads++;return[{result:{navigate:'https://research.ebsco.com/c/gsemyh/viewer/pdf/abc'}}];}
  return execute(args);
 };
 await h.controller.start('10.1287/mnsc.2018.3061');await flush();await flush();
 assert.equal(detailReads,1);assert.equal(h.actions.filter(x=>x[0]==='click-download').length,1);
 assert.equal(h.actions.filter(x=>x[0]==='route-update').length,2);
 assert.ok(h.actions.filter(x=>x[0]==='route-update').every(x=>x[1].active===false));
 await h.controller.stop();
});
