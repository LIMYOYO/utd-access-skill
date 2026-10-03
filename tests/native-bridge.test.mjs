import test from 'node:test';
import assert from 'node:assert/strict';
import {installNativeBridge} from '../src/native-bridge.js';
import {installDownloader} from '../src/downloader.js';
const event=()=>{const f=[];return{addListener:x=>f.push(x),fire:x=>f.forEach(y=>y(x))};};
const flush=()=>new Promise(r=>setImmediate(r));

test('single native disconnect prevents later navigation and download',async()=>{
 let resolvePublisher,clicks=0,navigations=0;
 const sent=[],storage={};
 const port={onMessage:event(),onDisconnect:event(),postMessage:m=>sent.push(m)};
 let tabUrl='https://pubsonline.informs.org/doi/10.1287/test.1';
 const api={
  runtime:{connectNative:()=>port,onMessage:event()},
  storage:{local:{get:async key=>({[key]:storage[key]}),set:async data=>Object.assign(storage,data)}},
  permissions:{contains:async()=>true},
  alarms:{create:async()=>{},clear:async()=>{},onAlarm:event()},
  downloads:{onCreated:event(),onChanged:event()},
  tabs:{create:async()=>({id:1}),get:async()=>({id:1,url:tabUrl,status:'complete'}),update:async()=>{navigations++;tabUrl='https://research.ebsco.com/c/x/viewer/pdf/one';}},
  scripting:{executeScript:async request=>{
   if(request.args[0]==='publisher')return new Promise(resolve=>{resolvePublisher=resolve;});
   if(request.args[0]==='click-download')clicks++;
   return [{result:{done:true}}];
  }}
 };
 const controller=installDownloader(api);
 installNativeBridge(api,controller,{reconnect:false});
 const session='11111111-1111-4111-8111-111111111111',id='22222222-2222-4222-8222-222222222222';
 port.onMessage.fire({v:1,type:'hello',session_id:session});await flush();
 port.onMessage.fire({v:1,type:'start',session_id:session,request_id:id,doi:'10.1287/test.1'});await flush();
 assert.equal(typeof resolvePublisher,'function');
 port.onDisconnect.fire();await flush();
 resolvePublisher([{result:{title:'Example title',href:'https://libkey.io/libraries/278/articles/1/full-text-file'}}]);await flush();await flush();
 assert.equal((await controller.status()).phase,'stopped');
 assert.equal(navigations,0);assert.equal(clicks,0);
 assert.equal(storage.bridgeConnection.connected,false);
});

test('single disconnect preserves a completed candidate for local validation',async()=>{
 const task={id:1,request_id:'22222222-2222-4222-8222-222222222222',phase:'downloaded_unverified',filename:'/tmp/paper.pdf',downloadId:8};
 const api={storage:{local:{get:async()=>({singlePaperTask:task}),set:async()=>{}}},downloads:{onCreated:event(),onChanged:event()},alarms:{onAlarm:event()},runtime:{onMessage:event()}};
 const controller=installDownloader(api);
 await controller.disconnect(task.request_id);
 assert.equal((await controller.status()).phase,'downloaded_unverified');
 assert.equal((await controller.status()).filename,task.filename);
});

test('single native disconnect cancels a permission-pending startup',async()=>{
 let resolvePermission,created=0;
 const storage={},port={onMessage:event(),onDisconnect:event(),postMessage:()=>{}};
 const api={
  runtime:{connectNative:()=>port,onMessage:event()},
  storage:{local:{get:async key=>({[key]:storage[key]}),set:async data=>Object.assign(storage,data)}},
  permissions:{contains:()=>new Promise(resolve=>{resolvePermission=resolve;})},
  alarms:{create:async()=>{},clear:async()=>{},onAlarm:event()},
  downloads:{onCreated:event(),onChanged:event()},
  tabs:{create:async()=>{created++;return{id:1};}}
 };
 const controller=installDownloader(api);
 installNativeBridge(api,controller,{reconnect:false});
 const session='11111111-1111-4111-8111-111111111111',id='22222222-2222-4222-8222-222222222222';
 port.onMessage.fire({v:1,type:'hello',session_id:session});await flush();
 port.onMessage.fire({v:1,type:'start',session_id:session,request_id:id,doi:'10.1287/test.1'});await flush();
 assert.equal(typeof resolvePermission,'function');
 port.onDisconnect.fire();await flush();
 resolvePermission(true);await flush();await flush();
 assert.equal(created,0);assert.equal(await controller.status(),null);
 assert.equal(controller.isBusy(),false);
});
test('pair close acknowledgment waits for controller seal and reports errors',async()=>{
 const sent=[];let finish;
 const port={onMessage:event(),onDisconnect:event(),postMessage:m=>sent.push(m)};
 const api={runtime:{connectNative:()=>port},storage:{local:{set:async()=>{}}}};
 const controller={subscribe:()=>{},status:async()=>null};
 const pairController={subscribe:()=>{},start:async()=>{},seal:()=>new Promise(resolve=>{finish=resolve;})};
 installNativeBridge(api,controller,{reconnect:false,pairController});
 const session='11111111-1111-4111-8111-111111111111',id='22222222-2222-4222-8222-222222222222';
 port.onMessage.fire({v:1,type:'hello',session_id:session});await flush();
 port.onMessage.fire({v:1,type:'start_pair',session_id:session,request_id:id,papers:[{request_id:'33333333-3333-4333-8333-333333333333',doi:'10.1287/a'},{request_id:'44444444-4444-4444-8444-444444444444',doi:'10.1287/b'}]});await flush();
 port.onMessage.fire({v:1,type:'seal_pair',session_id:session,request_id:id});await flush();
 assert.equal(typeof finish,'function');assert.equal(sent.some(m=>m.type==='pool_closed'),false);
 finish([8,9]);await flush();assert.deepEqual(sent.find(m=>m.type==='pool_closed').download_ids,[8,9]);
 pairController.seal=async()=>{throw Error('pool stopped');};
 port.onMessage.fire({v:1,type:'seal_pair',session_id:session,request_id:id});await flush();
 assert.equal(sent.at(-1).type,'error');assert.equal(sent.at(-1).reason,'pool stopped');
});
test('native bridge only accepts session-bound start once and reports candidate',async()=>{
 const port={onMessage:event(),onDisconnect:event(),postMessage:m=>sent.push(m),disconnect:()=>{}};
 const sent=[],starts=[];let notify;
 const controller={start:async(d,id)=>{starts.push(id);return{};},status:async()=>null,stop:async()=>{},subscribe:f=>{notify=f;},applyValidation:async()=>true};
 const api={runtime:{connectNative:()=>port},storage:{local:{set:async()=>{}}}};
 installNativeBridge(api,controller,{reconnect:false});
 const session='11111111-1111-4111-8111-111111111111',id='22222222-2222-4222-8222-222222222222';
 port.onMessage.fire({v:1,type:'hello',session_id:session});await flush();
 port.onMessage.fire({v:1,type:'start',session_id:session,request_id:id,doi:'10.1287/a'});await flush();
 port.onMessage.fire({v:1,type:'start',session_id:session,request_id:id,doi:'10.1287/a'});await flush();
 assert.equal(starts.length,1);
 notify({request_id:id,phase:'downloaded_unverified',downloadId:8,filename:'/tmp/a.pdf',title:'A',association:'candidate_no_referrer'});await flush();
 assert.equal(sent.filter(x=>x.type==='candidate').length,1);
 port.onMessage.fire({v:1,type:'start',session_id:'33333333-3333-4333-8333-333333333333',request_id:id,doi:'10.1287/a'});await flush();assert.equal(starts.length,1);
});


test('manual reconnect cancels a pending automatic retry',async()=>{
 const originalSet=globalThis.setTimeout,originalClear=globalThis.clearTimeout;
 const timers=new Map();let count=0;
 globalThis.setTimeout=fn=>{timers.set(++count,fn);return count;};globalThis.clearTimeout=id=>timers.delete(id);
 try {
  const ports=[];
  const api={runtime:{connectNative:()=>{const p={onMessage:event(),onDisconnect:event(),postMessage:()=>{},disconnect:()=>{}};ports.push(p);return p;}},storage:{local:{set:async()=>{}}}};
  const controller={subscribe:()=>{},status:async()=>null};
  const bridge=installNativeBridge(api,controller);
  ports[0].onDisconnect.fire();assert.equal(timers.size,1);
  bridge.reconnect();
  for(const fn of [...timers.values()])fn();
  assert.equal(ports.length,2,'a stale retry must not create an orphaned third connection');
 } finally {globalThis.setTimeout=originalSet;globalThis.clearTimeout=originalClear;}
});


test('batch adapter isolates child failure, emits candidates once, and seals after validation',async()=>{
 const sent=[],calls=[];let notify,complete;
 const port={onMessage:event(),onDisconnect:event(),postMessage:m=>sent.push(m)};
 const api={runtime:{connectNative:()=>port},storage:{local:{set:async()=>{}}}};
 const controller={subscribe:()=>{},status:async()=>null};
 const batchController={subscribe:f=>{notify=f;},start:async(...args)=>calls.push(args),applyPaperResult:async(...args)=>calls.push(args),seal:()=>new Promise(r=>{complete=r;}),stop:async()=>{},finish:async()=>{}};
 installNativeBridge(api,controller,{reconnect:false,batchController});
 const session='11111111-1111-4111-8111-111111111111',id='22222222-2222-4222-8222-222222222222',child='33333333-3333-4333-8333-333333333333';
 const message=(type,fields={})=>({v:1,type,session_id:session,request_id:id,...fields});
 port.onMessage.fire({v:1,type:'hello',session_id:session});await flush();
 port.onMessage.fire(message('start_batch',{papers:[{request_id:child,doi:'10.1287/test.1'}],concurrency:10}));await flush();
 assert.equal(calls[0][2],10);
 const snapshot={request_id:id,phase:'running',candidates:[{download_id:8,path:'/tmp/a.pdf'}],papers:[{request_id:child,phase:'needs_attention',reason:'no access'}]};
 notify(snapshot);notify(snapshot);
 assert.equal(sent.filter(m=>m.type==='batch_candidate').length,1);assert.equal(sent.filter(m=>m.type==='paper_failed').length,1);assert.equal(sent.some(m=>m.type==='error'),false);
 port.onMessage.fire(message('paper_result',{paper_id:child,status:'needs_attention',reason:'no access'}));await flush();assert.equal(calls.length,2);
 port.onMessage.fire(message('seal_batch'));await flush();assert.equal(sent.some(m=>m.type==='batch_closed'),false);
 complete([8]);await flush();assert.deepEqual(sent.at(-1).download_ids,[8]);
});
