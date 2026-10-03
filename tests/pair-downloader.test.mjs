import test from 'node:test';
import assert from 'node:assert/strict';
import {installPairDownloader} from '../src/pair-downloader.js';
const event=()=>{const f=[];return{addListener:x=>f.push(x),fire:x=>f.forEach(y=>y(x))};};
const flush=()=>new Promise(r=>setImmediate(r));
test('two independent tabs start and candidate order does not assign paper identity',async()=>{
 let next=0;const tabs=new Map(),clicked=[],memory={},items=new Map();
 const api={storage:{local:{get:async()=>memory,set:async v=>Object.assign(memory,v)}},permissions:{contains:async()=>true},alarms:{create:async()=>{},clear:async()=>{},onAlarm:event()},
 tabs:{create:async args=>{const tab={id:++next,...args};tabs.set(tab.id,tab);return tab;},get:async id=>tabs.get(id),update:async(id,args)=>{tabs.get(id).url='https://research.ebsco.com/c/x/viewer/pdf/'+id;}},
 scripting:{executeScript:async({target,args:[action,expected]})=>{if(action==='publisher')return[{result:{href:'https://libkey.io/libraries/278/articles/123/full-text-file',title:expected.doi}}];if(action==='click-download')clicked.push(target.tabId);return[{result:{done:true}}];}},
 downloads:{onCreated:event(),onChanged:event(),search:async({id})=>[items.get(id)]}};
 const c=installPairDownloader(api,{singleBusy:()=>false});await c.start('batch',[{request_id:'one',doi:'10.1287/a'},{request_id:'two',doi:'10.1287/b'}]);
 await flush();await flush();assert.equal(tabs.size,2);assert.equal(clicked.length,2);assert.equal(c.busy(),true);
 for(const id of [9,8]){const item={id,url:'blob:https://research.ebsco.com/opaque',referrer:'',startTime:new Date(Date.now()+1).toISOString(),state:'complete',mime:'application/pdf',filename:'/tmp/'+id+'.pdf'};items.set(id,item);api.downloads.onCreated.fire(item);}
 await flush();await flush();const state=await c.status();assert.equal(state.candidates.length,2);assert.equal(state.candidates[0].request_id,undefined);
 await c.seal('batch');
 await c.applyValidation('batch',{status:'verified_fulltext',reason:'verified',results:[{request_id:'two',status:'verified_fulltext',reason:''},{request_id:'one',status:'verified_fulltext',reason:''}]});assert.equal(c.busy(),false);
});

function fixture() {
 let next=0;const tabs=new Map(),memory={},items=new Map();
 const api={storage:{local:{get:async()=>memory,set:async v=>Object.assign(memory,v)}},permissions:{contains:async()=>true},alarms:{create:async()=>{},clear:async()=>{},onAlarm:event()},
 tabs:{create:async args=>{const tab={id:++next,...args};tabs.set(tab.id,tab);return tab;},get:async id=>tabs.get(id),update:async id=>{tabs.get(id).url='https://research.ebsco.com/c/x/viewer/pdf/'+id;}},
 scripting:{executeScript:async({args:[action]})=>[{result:action==='publisher'?{href:'https://libkey.io/libraries/278/articles/123/full-text-file',title:'paper'}:{done:true}}]},
 downloads:{onCreated:event(),onChanged:event(),search:async({id})=>[items.get(id)]}};
 const controller=installPairDownloader(api);
 const start=async batch=>{await controller.start(batch,[{request_id:'one',doi:'10.1287/a'},{request_id:'two',doi:'10.1287/b'}]);await flush();await flush();};
 const add=id=>{const item={id,url:'blob:https://research.ebsco.com/opaque',startTime:new Date(Date.now()+1).toISOString(),state:'complete',mime:'application/pdf',filename:'/tmp/'+id+'.pdf'};items.set(id,item);api.downloads.onCreated.fire(item);return item;};
 return {api,controller,start,add,items};
}
test('late rejection from old download check cannot stop replacement batch',async()=>{
 const f=fixture();let rejectOld;await f.start('old');
 f.api.downloads.search=()=>new Promise((resolve,reject)=>{rejectOld=reject;});f.add(1);await flush();
 await f.controller.stop('old');await f.start('replacement');rejectOld(Error('old search failed'));await flush();await flush();
 assert.equal((await f.controller.status()).request_id,'replacement');assert.equal(f.controller.busy(),true);await f.controller.stop('replacement');
});
test('seal waits for created checks and ignores later events',async()=>{
 const f=fixture();await f.start('batch');let finish;
 f.api.downloads.search=({id})=>id===1?new Promise(resolve=>{finish=()=>resolve([f.items.get(id)]);}):Promise.resolve([f.items.get(id)]);
 f.add(1);f.add(2);await flush();let sealed=false;const closing=f.controller.seal('batch').then(ids=>{sealed=true;return ids;});await flush();assert.equal(sealed,false);
 finish();assert.deepEqual((await closing).sort(),[1,2]);assert.equal((await f.controller.status()).sealed,true);
 f.add(3);f.api.downloads.onChanged.fire({id:1});await flush();assert.equal(f.controller.busy(),true);assert.equal((await f.controller.status()).candidates.length,2);await f.controller.stop('batch');
});
test('success requires seal and changed-check failure prevents seal',async()=>{
 const f=fixture();await f.start('batch');f.add(1);f.add(2);await flush();
 assert.equal(await f.controller.applyValidation('batch',{status:'verified_fulltext',results:[{request_id:'one',status:'verified_fulltext'},{request_id:'two',status:'verified_fulltext'}]}),false);
 let finish;f.api.downloads.search=()=>new Promise(resolve=>{finish=()=>resolve([{...f.items.get(1),state:'interrupted'}]);});f.api.downloads.onChanged.fire({id:1});await flush();
 const rejection=assert.rejects(f.controller.seal('batch'));finish();await rejection;assert.equal((await f.controller.status()).phase,'needs_attention');
});
test('third candidate prevents seal; replaced batch cannot be sealed by old waiter',async()=>{
 const f=fixture();await f.start('batch');f.add(1);f.add(2);f.add(3);await flush();await assert.rejects(f.controller.seal('batch'));
 const g=fixture();await g.start('old');let finish;g.api.downloads.search=()=>new Promise(resolve=>{finish=resolve;});g.add(1);await flush();
 const rejection=assert.rejects(g.controller.seal('old'));await g.controller.stop('old');await g.start('new');finish([g.items.get(1)]);await rejection;
 assert.equal((await g.controller.status()).request_id,'new');assert.equal((await g.controller.status()).sealed,false);await g.controller.stop('new');
});

test('late click response cannot overwrite verified terminal state',async()=>{
 const f=fixture(),release=[];const execute=f.api.scripting.executeScript;
 f.api.scripting.executeScript=args=>args.args[0]==='click-download'?new Promise(resolve=>release.push(()=>resolve([{result:{done:true}}]))):execute(args);
 await f.start('batch');assert.equal(release.length,2);f.add(1);f.add(2);await flush();await f.controller.seal('batch');
 assert.equal(await f.controller.applyValidation('batch',{status:'verified_fulltext',results:[{request_id:'one',status:'verified_fulltext'},{request_id:'two',status:'verified_fulltext'}]}),true);
 for(const finish of release)finish();await flush();await flush();
 assert.equal((await f.controller.status()).phase,'verified_fulltext');
});

test('both detail routes retain independent background tabs and click once each',async()=>{
 const f=fixture(),tabs=new Map(),updates=[],clicked=[];let id=0;
 f.api.tabs.create=async args=>{const tab={id:++id,...args};tabs.set(id,tab);return tab;};
 f.api.tabs.get=async id=>tabs.get(id);
 f.api.tabs.update=async(id,args)=>{updates.push({id,...args});tabs.get(id).url=args.url.startsWith('https://libkey.io')?'https://research.ebsco.com/c/gsemyh/search/details/record'+id:args.url;};
 f.api.scripting.executeScript=async({target,args:[action]})=>{
  const url=tabs.get(target.tabId).url;
  if(action==='publisher')return[{result:{title:'paper',href:'https://libkey.io/libraries/278/articles/123/content-location'}}];
  if(action==='viewer'&&url.includes('/search/details/'))return[{result:{navigate:'https://research.ebsco.com/c/gsemyh/viewer/pdf/record'+target.tabId}}];
  if(action==='click-download')clicked.push(target.tabId);
  return[{result:{done:true}}];
 };
 await f.start('batch');assert.deepEqual(clicked.sort(),[1,2]);assert.equal(updates.length,4);assert.ok(updates.every(x=>x.active===false));await f.controller.stop('batch');
});
