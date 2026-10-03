"""Chrome-owned native host. No network listener and no arbitrary command execution."""
import fcntl
import json
import queue as queues
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
from .protocol import read_message,write_message,validate_message
from .queue import BridgeQueue
from .validation import validate_candidate
from .ssrn import validate_ssrn_candidate
from ..store import JobStore


def serve(stdin,stdout,origin,config,queue):
    if origin!='chrome-extension://'+config['extension_id']+'/':raise ValueError('unpaired_extension')
    lock_path=Path(config['data_dir'])/'bridge-host.lock'
    with lock_path.open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('another_bridge_connected')
        return _serve(stdin,stdout,config,queue)


def _serve(stdin,stdout,config,queue):
    session=str(uuid4());inbox=queues.Queue();handshake=False;current=None;pending=None;ended=False
    def reader():
        try:
            while True:
                value=read_message(stdin);inbox.put(value)
                if value is None:return
        except Exception:inbox.put(None)
    def send(kind,**fields):write_message(stdout,validate_message({'v':1,'type':kind,'session_id':session,**fields},'host'))
    queue.connect(session)
    executor=ThreadPoolExecutor(max_workers=1)
    try:
        send('hello');threading.Thread(target=reader,daemon=True).start()
        hello_deadline=time.monotonic()+10
        while not ended:
            try:message=inbox.get(timeout=0.25)
            except queues.Empty:message='tick'
            if message is None:ended=True;break
            if message!='tick':
                message=validate_message(message,'extension')
                if message['session_id']!=session:continue
                if message['type']=='hello':handshake=True
                elif handshake:
                    rid=message['request_id']
                    try:record=queue.get(rid)
                    except ValueError:continue
                    if message['type'] in ('candidate','ssrn_candidate') and current is None and record['state'] in ('verified_fulltext','downloaded_fulltext','needs_attention','failed','cancelled'):
                        send('validation_result',request_id=rid,status=record['state'],reason=record['payload'].get('message',record['payload'].get('reason','')))
                        continue
                    if message['type'] in ('candidate','ssrn_candidate') and current is None and record['state']=='downloaded_unverified':
                        # Recovery is file validation only, not a repeated browser action.
                        with queue.db() as db:
                            db.execute("UPDATE requests SET session_id=? WHERE request_id=? AND state='downloaded_unverified'",(session,rid))
                        current=rid;record=queue.get(rid)
                    if current!=rid or record['session_id']!=session:continue
                    if message['type'] in ('ack','progress'):
                        queue.transition(rid,session,('dispatched','downloading'),'downloading',{'phase':message.get('phase','ack')})
                    elif message['type']=='error':
                        queue.transition(rid,session,('dispatched','downloading','downloaded_unverified','verifying'),'needs_attention',{'reason':message['reason']})
                    elif message['type'] in ('candidate','ssrn_candidate'):
                        if (message['type']=='ssrn_candidate') != record['doi'].startswith('10.2139/ssrn.'):continue
                        if pending is not None:continue
                        if queue.transition(rid,session,('dispatched','downloading','downloaded_unverified'),'downloaded_unverified',{'candidate':message}):
                            request=queue.get(rid)
                            queue.transition(rid,session,('downloaded_unverified',),'verifying',{'candidate':message})
                            store=JobStore(Path(config['data_dir'])/'jobs.sqlite3')
                            validator=validate_ssrn_candidate if message['type']=='ssrn_candidate' else validate_candidate
                            pending=executor.submit(validator,request,message,config,store)
            if not queue.heartbeat(session):raise ValueError('connection_owner_lost')
            if not handshake:
                if time.monotonic()>hello_deadline:raise ValueError('handshake_timeout')
                continue
            if current:
                record=queue.get(current)
                if record['state']=='cancelled':send('cancel',request_id=current)
                if pending is not None and pending.done():
                    try:result=pending.result()
                    except Exception as error:result={'status':'needs_attention','reason':type(error).__name__+': '+str(error)[:500]}
                    queue.transition(current,session,('verifying',),result['status'],result)
                    pending=None;record=queue.get(current)
                if record['state'] in ('verified_fulltext','downloaded_fulltext','needs_attention','failed','cancelled') and pending is None:
                    send('validation_result',request_id=current,status=record['state'],reason=record['payload'].get('message',record['payload'].get('reason','')))
                    current=None
                elif time.time()>record['expires'] and record['state']!='verifying':
                    send('cancel',request_id=current)
                    queue.transition(current,session,('dispatched','downloading'),'needs_attention',{'reason':'request_deadline_exceeded'})
            if current is None and pending is None:
                record=queue.claim(session)
                if record:
                    if record['payload'].get('experiment')=='parallel_batch':
                        from .batch import run_batch
                        ended=run_batch(record,session,config,queue,inbox,send)
                    elif record['payload'].get('experiment')=='parallel_pair':
                        from .pair import run_pair
                        ended=run_pair(record,session,config,queue,inbox,send)
                    else:
                        current=record['request_id']
                        if record['doi'].startswith('10.2139/ssrn.'):
                            send('start_ssrn',request_id=current,ssrn_id=record['doi'].split('.')[-1])
                        else:send('start',request_id=current,doi=record['doi'])
        return 0
    finally:
        executor.shutdown(wait=True)
        # Persist recoverable candidate; do not repeat a download after disconnect.
        if current:
            record=queue.get(current)
            if pending is not None:
                try:result=pending.result();queue.transition(current,session,('verifying',),result['status'],result)
                except Exception:queue.transition(current,session,('verifying',),'needs_attention',{'reason':'validation_interrupted'})
        queue.disconnect(session)


def main(argv=None):
    args=sys.argv[1:] if argv is None else argv
    if len(args)!=2:return 2
    config=json.loads(Path(args[0]).read_text())
    queue=BridgeQueue(Path(config['data_dir'])/'bridge.sqlite3')
    try:return serve(sys.stdin.buffer,sys.stdout.buffer,args[1],config,queue)
    except Exception as error:
        print('utd-paper-access bridge: '+type(error).__name__+': '+str(error),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
