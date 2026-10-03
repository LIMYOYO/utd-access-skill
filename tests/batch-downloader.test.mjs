import test from 'node:test';
import assert from 'node:assert/strict';
import {installBatchDownloader} from '../src/batch-downloader.js';
const event=()=>{const listeners=[];return{addListener:f=>listeners.push(f),fire:x=>listeners.forEach(f=>f(x))};};
const flush=()=>new Promise(r=>setImmediate(r));
function fixture(failing=[]) {
 const memory={},tabs=new Map(),clicks=[],items=new Map();let id=0;
 const api={storage:{local:{get:async()=>memory,set:async x=>Object.assign(memory,x)}},permissions:{contains:async()=>true},alarms:{create:async()=>{},clear:async()=>{},onAlarm:event()},
 tabs:{create:async args=>{const t={id:++id,...args};tabs.set(id,t);return t;},get:async id=>tabs.get(id),update:async(id,args)=>{tabs.get(id).url='https://research.ebsco.com/c/x/viewer/pdf/record'+id;}},
 scripting:{executeScript:async({target,args:[action,expected]})=>{
  if(action==='publisher'&&failing.includes(expected.doi))return[{result:{error:'no full text'}}];
  if(action==='publisher')return[{result:{title:expected.doi,href:'https://libkey.io/libraries/278/articles/1/full-text-file'}}];
  if(action==='click-download')clicks.push(target.tabId);
  return[{result:{done:true}}];
 }},downloads:{onCreated:event(),onChanged:event(),search:async({id})=>[items.get(id)]}};
 const c=installBatchDownloader(api),papers=Array.from({length:10},(_,i)=>({request_id:'p'+i,doi:'10.1287/test.'+i}));
 const start=async(n,concurrency)=>{await c.start('batch',papers.slice(0,n),concurrency);await flush();await flush();};
 const add=id=>{const item={id,url:'blob:https://research.ebsco.com/a',startTime:new Date(Date.now()+1).toISOString(),state:'complete',mime:'application/pdf',filename:'/tmp/'+id+'.pdf'};items.set(id,item);api.downloads.onCreated.fire(item);};
 return {api,c,papers,tabs,clicks,start,add};
}
test('ten papers can start simultaneously in independent inactive tabs',async()=>{
 const f=fixture();await f.start(10,10);assert.equal(f.tabs.size,10);assert.equal(f.clicks.length,10);assert.ok([...f.tabs.values()].every(t=>t.active===false));await f.c.stop('batch');
});
test('slot opens after individual validation and failure does not stop peers',async()=>{
 const f=fixture(['10.1287/test.0']);await f.start(5,2);assert.equal(f.tabs.size,3);assert.equal(f.c.busy(),true);
 let s=await f.c.status();assert.equal(s.papers[0].phase,'needs_attention');
 await f.c.applyPaperResult('batch','p1',{status:'verified_fulltext',reason:'verified'});await flush();await flush();assert.equal(f.tabs.size,4);
 s=await f.c.status();assert.equal(s.papers[1].phase,'verified_fulltext');assert.equal(s.papers[2].phase,'waiting_download');await f.c.stop('batch');
});
test('reverse candidates remain unassigned; sealed completion preserves successful children',async()=>{
 const f=fixture(['10.1287/test.0']);await f.start(3,3);f.add(9);f.add(8);await flush();await flush();
 let s=await f.c.status();assert.equal(s.candidates.length,2);assert.equal(s.candidates[0].paper_id,undefined);
 for(const id of ['p1','p2'])await f.c.applyPaperResult('batch',id,{status:'verified_fulltext',reason:'verified'});
 assert.deepEqual((await f.c.seal('batch')).sort(),[8,9]);
 await f.c.finish('batch',{status:'needs_attention',reason:'partial',results:s.papers.map(p=>({request_id:p.request_id,status:p.request_id==='p0'?'needs_attention':'verified_fulltext',reason:''}))});
 s=await f.c.status();assert.equal(s.papers[1].phase,'verified_fulltext');assert.equal(s.phase,'needs_attention');assert.equal(f.c.busy(),false);
});
test('old search rejection and late click cannot overwrite completed or replacement papers',async()=>{
 const f=fixture();await f.start(2,2);let reject;
 f.api.downloads.search=()=>new Promise((resolve,r)=>{reject=r;});f.add(1);await flush();
 await f.c.stop('batch');await f.c.start('new',f.papers.slice(0,2),2);reject(Error('old failure'));await flush();
 assert.equal((await f.c.status()).request_id,'new');assert.equal(f.c.busy(),true);await f.c.stop('new');
});


test('all ten tabs open but only two authentication routes overlap',async()=>{
 const f=fixture();const update=f.api.tabs.update,execute=f.api.scripting.executeScript;
 const entered=[],release=[];
 f.api.tabs.update=async(...args)=>{entered.push(args[0]);return update(...args);};
 f.api.scripting.executeScript=async arg=>{
  if(arg.args[0]==='viewer')await new Promise(r=>release.push(r));
  return execute(arg);
 };
 await f.start(10,10);assert.equal(f.tabs.size,10);assert.equal(entered.length,2);
 release.shift()();await new Promise(r=>setTimeout(r,550));await flush();assert.equal(entered.length,3);
 assert.equal(f.clicks.length,1,'the first paper proceeds while its peer is still authenticating');
 await f.c.stop('batch');for(const resolve of release)resolve();await flush();
});
