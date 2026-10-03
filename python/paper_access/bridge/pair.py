"""Two-paper experiment: identify candidates by primary DOI, never event order."""
import hashlib
import queue as queues
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from ..extract import read_document
from ..models import Artifact
from ..imports import normalize_identifier
from ..store import JobStore
from .validation import stage_candidate,validate_candidate
from .protocol import validate_message


def identify_candidate(pdf,papers):
    digest=hashlib.sha256(Path(pdf).read_bytes()).hexdigest()
    document=read_document(Artifact(Path(pdf),digest,'application/pdf',Path(pdf).stat().st_size))
    primary={normalize_identifier(doi) for doi in document.primary_dois}
    front={normalize_identifier(doi) for doi in document.front_matter_dois}
    matches=[p['request_id'] for p in papers if primary=={normalize_identifier(p['doi'])} and (not front or front==primary)]
    if len(matches)!=1:raise ValueError('candidate_doi_not_unique_in_pair')
    return matches[0]


def process_candidate(message,papers,config):
    staged=stage_candidate(message['path'],Path(config['download_root']),Path(config['data_dir'])/'pair-staging')
    try:
        rid=identify_candidate(staged,papers)
        request=next(p for p in papers if p['request_id']==rid)
        # The original user-controlled file cannot change the DOI after classification.
        staged_config={**config,'download_root':str(staged.parent)}
        result=validate_candidate(request,{'path':str(staged),'title':''},staged_config,JobStore(Path(config['data_dir'])/'jobs.sqlite3'))
        return rid,result
    finally:staged.unlink(missing_ok=True)


def run_pair(record,session,config,queue,inbox,send):
    batch=record['request_id'];papers=[{**p,'validation_policy':record.get('validation_policy','strict'),'version_policy':record.get('version_policy','best-available')} for p in record['payload']['papers']];futures={};seen=set();results={};failure=None;ended=False
    sealing=False;closed=False
    def report(status,reason):
        send('pair_result',request_id=batch,status=status,reason=reason,results=[{'request_id':rid,'status':r['status'],'reason':r.get('reason','')} for rid,r in results.items()])
    send('start_pair',request_id=batch,papers=[{'request_id':p['request_id'],'doi':p['doi']} for p in papers])
    queue.transition(batch,session,('dispatched',),'downloading',{'papers':papers,'experiment':'parallel_pair'})
    with ThreadPoolExecutor(max_workers=2) as pool:
        while not closed and not failure:
            try:message=inbox.get(timeout=0.25)
            except queues.Empty:message='tick'
            if message is None:failure='bridge_disconnected_no_replay';ended=True;break
            if message!='tick':
                message=validate_message(message,'extension')
                if message['session_id']!=session or message.get('request_id')!=batch:continue
                if message['type']=='error':failure=message['reason'];break
                if message['type']=='pool_closed':
                    if not sealing or set(message['download_ids'])!=seen:
                        failure='unexpected_pool_close';break
                    closed=True
                if message['type']=='pool_candidate':
                    did=message['download_id']
                    if did in seen:continue
                    seen.add(did)
                    if len(seen)>2:failure='multiple_download_candidates';break
                    futures[did]=pool.submit(process_candidate,message,papers,config)
            if not queue.heartbeat(session):failure='connection_owner_lost';break
            current=queue.get(batch)
            if current['state']=='cancelled':failure='cancelled';break
            if time.time()>record['expires']:failure='pair_deadline_exceeded';break
            for did,future in list(futures.items()):
                if not future.done():continue
                del futures[did]
                try:rid,result=future.result()
                except Exception as exc:failure=type(exc).__name__+': '+str(exc)[:400];break
                if rid in results:failure='duplicate_doi_candidates';break
                results[rid]=result
                if result['status'] not in ('verified_fulltext','downloaded_fulltext'):failure=result.get('reason','validation_failed');break
            # Completion requires an ordered acknowledgment from the browser.
            # Errors already queued on its port are consumed before pool_closed.
            if len(results)==2 and not failure and not sealing:
                sealing=True
                send('seal_pair',request_id=batch)
        status='needs_attention' if failure else 'verified_fulltext' if all(r['status']=='verified_fulltext' for r in results.values()) else 'downloaded_fulltext'
        payload={'papers':papers,'results':results,'experiment':'parallel_pair','reason':failure or 'verified'}
        queue.transition(batch,session,('downloading',),status,payload)
        current=queue.get(batch)
        if not ended:
            if failure:send('cancel',request_id=batch)
            report(current['state'],failure or 'verified')
    return ended
