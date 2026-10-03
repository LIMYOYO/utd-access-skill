// Native port is available only to this extension background, never content scripts.
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
export function installNativeBridge(api,controller,{reconnect=true,pairController=null,batchController=null,ssrnController=null}={}) {
  let pairMode=false,batchMode=false,ssrnMode=false;
  let port,session,request,retryTimer,connectionGeneration=0,attempt=0,serial=Promise.resolve();
  const seen=new Set(),reported=new Set();
  const state=(connected,message)=>api.storage.local.set({bridgeConnection:{connected,message}});
  const send=message=>{if(port && session)port.postMessage({v:1,session_id:session,...message});};
  const publish=task=>{
    if(!task || task.request_id!==request || !session)return;
    if(task.phase==='downloaded_unverified' && !reported.has(request)) {
      reported.add(request);
      send({type:'candidate',request_id:request,download_id:task.downloadId,path:task.filename,title:task.title||'',association:task.association||''});
    } else if(['stopped','failed','needs_attention','cancelled'].includes(task.phase)) {
      send({type:'error',request_id:request,reason:task.message||task.phase});
    } else if(['publisher','viewer','waiting_download'].includes(task.phase)) {
      send({type:'progress',request_id:request,phase:task.phase});
    }
  };
  controller.subscribe(task=>{if(!pairMode&&!batchMode&&!ssrnMode)publish(task);});
  ssrnController?.subscribe(task=>{
    if(!ssrnMode||task?.request_id!==request||!session)return;
    if(task.phase==='downloaded_unverified'&&!reported.has(request)){
      reported.add(request);send({type:'ssrn_candidate',request_id:request,ssrn_id:task.ssrn_id,download_id:task.downloadId,path:task.filename,title:task.title,authors:task.authors});
    }else if(['needs_attention','failed','cancelled'].includes(task.phase))send({type:'error',request_id:request,reason:task.message});
    else if(['publisher','waiting_download'].includes(task.phase))send({type:'progress',request_id:request,phase:task.phase});
  });
  pairController?.subscribe(task=>{
    if(!pairMode || task?.request_id!==request || !session)return;
    for(const candidate of task.candidates||[]) {
      const key=request+':'+candidate.download_id;
      if(!reported.has(key)){reported.add(key);send({type:'pool_candidate',request_id:request,download_id:candidate.download_id,path:candidate.path});}
    }
    if(task.phase==='needs_attention')send({type:'error',request_id:request,reason:task.message});
  });
  batchController?.subscribe(task=>{
    if(!batchMode || task?.request_id!==request || !session)return;
    for(const candidate of task.candidates||[]) {
      const key=request+':download:'+candidate.download_id;
      if(!reported.has(key)){reported.add(key);send({type:'batch_candidate',request_id:request,download_id:candidate.download_id,path:candidate.path});}
    }
    if(task.phase==='running')for(const paper of task.papers||[]) {
      const key=request+':paper:'+paper.request_id;
      if(['needs_attention','failed','cancelled'].includes(paper.phase)&&!reported.has(key)) {
        reported.add(key);send({type:'paper_failed',request_id:request,paper_id:paper.request_id,reason:paper.reason||paper.phase});
      }
    }
    if(task.phase==='needs_attention'&&!reported.has(request+':fatal')) {
      reported.add(request+':fatal');send({type:'error',request_id:request,reason:task.message});
    }
  });
  async function receive(message,currentPort) {
    if(currentPort!==port || !message || message.v!==1 || !UUID.test(message.session_id||''))return;
    const required={start_ssrn:['v','type','session_id','request_id','ssrn_id'],start_batch:['v','type','session_id','request_id','papers','concurrency'],paper_result:['v','type','session_id','request_id','paper_id','status','reason'],seal_batch:['v','type','session_id','request_id'],batch_result:['v','type','session_id','request_id','results','status','reason'],seal_pair:['v','type','session_id','request_id'],start_pair:['v','type','session_id','request_id','papers'],pair_result:['v','type','session_id','request_id','results','status','reason'],hello:['v','type','session_id'],start:['v','type','session_id','request_id','doi'],cancel:['v','type','session_id','request_id'],validation_result:['v','type','session_id','request_id','status','reason']}[message.type];
    if(!required || Object.keys(message).length!==required.length || required.some(k=>!(k in message)))return;
    if(message.type==='hello') {
      if(session)return;
      session=message.session_id;
      const single=await controller.status(),ssrn=await ssrnController?.status();
      const existing=ssrn?.phase==='downloaded_unverified'?ssrn:single;ssrnMode=existing===ssrn&&Boolean(ssrn);
      if(currentPort!==port)return;
      // A persisted unverified candidate is offered again; never replay start.
      request=existing?.request_id;
      send({type:'hello'});await state(true,'Codex 本地连接已就绪');
      if(request){if(ssrnMode&&existing.phase==='downloaded_unverified'){reported.add(request);send({type:'ssrn_candidate',request_id:request,ssrn_id:existing.ssrn_id,download_id:existing.downloadId,path:existing.filename,title:existing.title,authors:existing.authors});}else publish(existing);}
      return;
    }
    if(message.session_id!==session || !UUID.test(message.request_id||''))return;
    if(message.type==='start_ssrn') {
      if(!ssrnController||seen.has(message.request_id)||! /^[1-9]\d{0,9}$/.test(message.ssrn_id||''))return;
      seen.add(message.request_id);request=message.request_id;pairMode=false;batchMode=false;ssrnMode=true;
      try{await ssrnController.start(message.ssrn_id,request);send({type:'ack',request_id:request});}
      catch(error){send({type:'error',request_id:request,reason:String(error.message).slice(0,4000)});}
    } else if(message.type==='start_batch') {
      if(!batchController || seen.has(message.request_id) || !Array.isArray(message.papers) || message.papers.length<1 || message.papers.length>10 || !Number.isInteger(message.concurrency) || message.concurrency<1 || message.concurrency>10 || message.papers.some(p=>!p || !UUID.test(p.request_id||'') || typeof p.doi!=='string'))return;
      seen.add(message.request_id);request=message.request_id;pairMode=false;batchMode=true;ssrnMode=false;
      try {await batchController.start(request,message.papers,message.concurrency);send({type:'ack',request_id:request});}
      catch(error){send({type:'error',request_id:request,reason:String(error.message).slice(0,4000)});}
    } else if(message.type==='start_pair') {
      if(!pairController || seen.has(message.request_id) || !Array.isArray(message.papers) || message.papers.length!==2 || message.papers.some(p=>!p || !UUID.test(p.request_id||'') || typeof p.doi!=='string'))return;
      seen.add(message.request_id);request=message.request_id;pairMode=true;batchMode=false;ssrnMode=false;
      try {await pairController.start(request,message.papers);send({type:'ack',request_id:request});}
      catch(error){send({type:'error',request_id:request,reason:String(error.message)});}
    } else if(message.type==='start') {
      pairMode=false;batchMode=false;ssrnMode=false;
      if(typeof message.doi!=='string' || message.doi.length>256)return;
      if(seen.has(message.request_id))return;
      seen.add(message.request_id);request=message.request_id;
      try { await controller.start(message.doi,request);send({type:'ack',request_id:request});publish(await controller.status()); }
      catch(error){send({type:'error',request_id:request,reason:String(error.message).slice(0,4000)});}
    } else if(message.request_id===request && message.type==='cancel') {
      if(ssrnMode)await ssrnController.stop(request);else if(batchMode)await batchController.stop(request);else if(pairMode)await pairController.stop(request);else await controller.stop(request);
     } else if(message.request_id===request && message.type==='paper_result' && batchMode) {
      if(!UUID.test(message.paper_id||'') || typeof message.reason!=='string' || message.reason.length>4096)return;
      await batchController.applyPaperResult(request,message.paper_id,message);
    } else if(message.request_id===request && message.type==='seal_batch' && batchMode) {
      const batch=request;
      try {
        const ids=await batchController.seal(batch);
        if(currentPort===port && request===batch)send({type:'batch_closed',request_id:batch,download_ids:ids});
      } catch(error) {
        if(currentPort===port && request===batch)send({type:'error',request_id:batch,reason:String(error.message).slice(0,4000)});
      }
    } else if(message.request_id===request && message.type==='batch_result' && batchMode) {
      if(!Array.isArray(message.results) || message.results.length>10 || typeof message.reason!=='string')return;
      await batchController.finish(request,message);
    } else if(message.request_id===request && message.type==='seal_pair'  && pairMode) {
      const batch=request;
      try {
        const ids=await pairController.seal(batch);
        if(currentPort===port && request===batch)send({type:'pool_closed',request_id:batch,download_ids:ids});
      } catch(error) {
        if(currentPort===port && request===batch)send({type:'error',request_id:batch,reason:String(error.message).slice(0,4000)});
      }
    } else if(message.request_id===request && message.type==='pair_result' && pairMode) {
      if(!Array.isArray(message.results) || message.results.length>2 || typeof message.reason!=='string')return;
      await pairController.applyValidation(request,message);
    } else if(message.request_id===request && message.type==='validation_result') {
      if(typeof message.reason!=='string' || message.reason.length>4096)return;
      if(ssrnMode)await ssrnController.applyValidation(request,message);else await controller.applyValidation(request,message);
    }
  }
  function connect() {
    if(port)return;
    if(retryTimer!==undefined){clearTimeout(retryTimer);retryTimer=undefined;}
    const generation=++connectionGeneration;
    session=null;reported.clear();
    try {
      const current=api.runtime.connectNative('com.paper_access.bridge');port=current;
      current.onMessage.addListener(message=>{serial=serial.then(()=>receive(message,current)).catch(error=>state(false,String(error.message).slice(0,500)));});
      current.onDisconnect.addListener(()=>{
        if(port!==current)return;
        // Read lastError inside the callback so Chrome does not report it as unchecked.
        const nativeError=api.runtime.lastError?.message;
        port=null;session=null;if(ssrnMode)void ssrnController.disconnect(request);else if(batchMode)void batchController.stop(request);else if(pairMode)void pairController.stop(request);else if(request)void controller.disconnect(request);void state(false,'本地连接断开；未完成任务不会自动重下。'+(nativeError?' '+nativeError:''));
        if(reconnect && attempt<3)retryTimer=setTimeout(()=>{
          retryTimer=undefined;
          if(generation===connectionGeneration && !port)connect();
        },[1000,5000,15000][attempt++]);
      });
    } catch(error){void state(false,String(error.message).slice(0,500));}
  }
  connect();
  return {reconnect:()=>{if(!port){attempt=0;connect();}}};
}
