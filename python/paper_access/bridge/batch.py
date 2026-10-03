"""Independent browser tasks; PDFs are attributed by immutable primary DOI."""
import queue as queues
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from ..store import JobStore
from .pair import identify_candidate
from .validation import stage_candidate, validate_candidate
from .protocol import validate_message


def process_candidate(message, papers, config, store):
    staged=stage_candidate(message['path'],Path(config['download_root']),Path(config['data_dir'])/'batch-staging')
    try:
        rid=identify_candidate(staged,papers)
        request=next(p for p in papers if p['request_id']==rid)
        result=validate_candidate(request,{'path':str(staged),'title':''},{**config,'download_root':str(staged.parent)},store)
        return rid,result
    finally:
        staged.unlink(missing_ok=True)


def run_batch(record,session,config,queue,inbox,send):
    batch=record['request_id'];papers=[{**p,'validation_policy':record.get('validation_policy','strict'),'version_policy':record.get('version_policy','best-available')} for p in record['payload']['papers']];ids={p['request_id'] for p in papers}
    concurrency=record['payload']['concurrency'];results={};futures={};seen=set();fatal=None;closed=False;sealing=False;ended=False
    # Initialize schema before launching concurrent readers/writers.
    store=JobStore(Path(config['data_dir'])/'jobs.sqlite3')
    def persist(status='downloading',reason='in_progress'):
        payload={'papers':papers,'concurrency':concurrency,'results':results,'experiment':'parallel_batch','reason':reason}
        queue.transition(batch,session,('cancelled',) if status=='cancelled' else ('downloading',),status,payload)
    def result_for(rid,result):
        if rid in results and not (results[rid]['status'] in ('verified_fulltext','downloaded_fulltext') and result['status'] not in ('verified_fulltext','downloaded_fulltext')):return
        results[rid]=result;persist()
        send('paper_result',request_id=batch,paper_id=rid,status=result['status'],reason=result.get('reason',''))
    send('start_batch',request_id=batch,papers=[{'request_id':p['request_id'],'doi':p['doi']} for p in papers],concurrency=concurrency)
    queue.transition(batch,session,('dispatched',),'downloading',{'papers':papers,'concurrency':concurrency,'results':{},'experiment':'parallel_batch'})
    with ThreadPoolExecutor(max_workers=min(concurrency,4)) as pool:
        while not closed and not fatal:
            try:message=inbox.get(timeout=0.25)
            except queues.Empty:message='tick'
            if message is None:fatal='bridge_disconnected_no_replay';ended=True;break
            if message!='tick':
                message=validate_message(message,'extension')
                if message['session_id']!=session or message.get('request_id')!=batch:continue
                if message['type']=='error':fatal=message['reason'];break
                if message['type']=='paper_failed':
                    if message['paper_id'] not in ids:fatal='unknown_paper_id';break
                    result_for(message['paper_id'],{'status':'needs_attention','reason':message['reason']})
                elif message['type']=='batch_candidate':
                    if sealing:fatal='candidate_after_seal';break
                    did=message['download_id']
                    if did in seen:continue
                    seen.add(did)
                    if len(seen)>len(papers):fatal='multiple_download_candidates';break
                    futures[did]=pool.submit(process_candidate,message,papers,config,store)
                elif message['type']=='batch_closed':
                    if not sealing or set(message['download_ids'])!=seen:fatal='unexpected_batch_close';break
                    closed=True
            if not queue.heartbeat(session):fatal='connection_owner_lost';break
            if queue.get(batch)['state']=='cancelled':fatal='cancelled';break
            if time.time()>record['expires']:fatal='batch_deadline_exceeded';break
            for did,future in list(futures.items()):
                if not future.done():continue
                del futures[did]
                try:rid,result=future.result()
                except Exception as exc:fatal=type(exc).__name__+': '+str(exc)[:400];break
                if rid not in ids:fatal='unknown_candidate_paper';break
                if rid in results:
                    if results[rid]['status'] in ('verified_fulltext','downloaded_fulltext'):fatal='duplicate_doi_candidates';break
                    # A late file does not replay or promote a failed browser task.
                    continue
                result_for(rid,result)
            if len(results)==len(papers) and not futures and not fatal and not sealing:
                sealing=True;send('seal_batch',request_id=batch)
        if fatal:
            for rid in ids-results.keys():results[rid]={'status':'cancelled' if fatal=='cancelled' else 'needs_attention','reason':fatal}
        status='verified_fulltext' if not fatal and all(r['status']=='verified_fulltext' for r in results.values()) else 'downloaded_fulltext' if not fatal and all(r['status'] in ('verified_fulltext','downloaded_fulltext') for r in results.values()) else 'needs_attention'
        if fatal=='cancelled':status='cancelled'
        reason=fatal or ('verified' if status=='verified_fulltext' else 'downloaded_identity_unverified' if status=='downloaded_fulltext' else 'partial_failure')
        persist(status,reason)
        current=queue.get(batch)
        if current['state']=='cancelled' and status!='cancelled':
            status='cancelled';reason='cancelled'
            for rid in ids:
                if results.get(rid,{}).get('status') not in ('verified_fulltext','downloaded_fulltext'):results[rid]={'status':'cancelled','reason':'cancelled'}
            persist(status,reason)
        elif current['state']!=status:
            status='needs_attention';reason='connection_owner_lost'
        if not ended:
            if fatal:send('cancel',request_id=batch)
            send('batch_result',request_id=batch,status=status,reason=reason,results=[{'request_id':rid,'status':r['status'],'reason':r.get('reason','')} for rid,r in results.items()])
    return ended
