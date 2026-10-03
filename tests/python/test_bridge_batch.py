import queue
import os
from concurrent.futures import Future
from uuid import uuid4
import pytest
from paper_access.bridge.protocol import validate_message
from paper_access.bridge.batch import run_batch
from paper_access.bridge.queue import BridgeQueue


def test_batch_protocol_accepts_ten_distinct_papers():
    message={'v':1,'type':'start_batch','session_id':str(uuid4()),'request_id':str(uuid4()),'concurrency':10,'papers':[{'request_id':str(uuid4()),'doi':f'10.1287/test.{i}'} for i in range(10)]}
    assert validate_message(message,'host')==message
    for bad in [0,11,True]:
        with pytest.raises(ValueError):validate_message({**message,'concurrency':bad},'host')
    message['papers'][1]['doi']=message['papers'][0]['doi']
    with pytest.raises(ValueError):validate_message(message,'host')


@pytest.mark.parametrize('unexpected',[False,True])
def test_child_failure_is_isolated_and_close_gate_catches_unknown_candidate(monkeypatch,tmp_path,unexpected):
    from paper_access.bridge import batch
    q=BridgeQueue(tmp_path/'bridge.sqlite3');session=str(uuid4());q.connect(session)
    papers=[{'request_id':str(uuid4()),'doi':f'10.1287/test.{i}','output_dir':str(tmp_path/f'out{i}')} for i in range(3)]
    q.submit(papers[0]['doi'],tmp_path,payload={'experiment':'parallel_batch','papers':papers,'concurrency':3});record=q.claim(session);inbox=queue.Queue();sent=[]
    def msg(kind,**kwargs):return {'v':1,'type':kind,'session_id':session,'request_id':record['request_id'],**kwargs}
    inbox.put(msg('paper_failed',paper_id=papers[0]['request_id'],reason='no full text'))
    for i in [2,1]:inbox.put(msg('batch_candidate',download_id=i,path=f'/tmp/{i}.pdf'))
    if unexpected:inbox.put(msg('batch_candidate',download_id=99,path='/tmp/99.pdf'))
    class Pool:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def submit(self,fn,message,*args):
            f=Future()
            if message['download_id']==99:f.set_exception(ValueError('unknown DOI'))
            else:f.set_result((papers[message['download_id']]['request_id'],{'status':'verified_fulltext','reason':'verified'}))
            return f
    monkeypatch.setattr(batch,'ThreadPoolExecutor',Pool)
    def send(kind,**fields):
        sent.append((kind,fields))
        if kind=='seal_batch':inbox.put(msg('batch_closed',download_ids=[2,1] if not unexpected else [2,1,99]))
    run_batch(record,session,{'data_dir':str(tmp_path)},q,inbox,send)
    result=q.get(record['request_id']);children=result['payload']['results']
    assert len(children)==3
    assert children[papers[0]['request_id']]['status']=='needs_attention'
    assert children[papers[1]['request_id']]['status']=='verified_fulltext'
    assert children[papers[2]['request_id']]['status']=='verified_fulltext'
    assert result['state']=='needs_attention'
    if unexpected:assert result['payload']['reason']!='partial_failure'
    else:assert len([x for x in sent if x[0]=='paper_result'])==3


@pytest.mark.parametrize('race',['late_failure','after_seal','cancel'])
def test_batch_completion_races(monkeypatch,tmp_path,race):
    from paper_access.bridge import batch
    q=BridgeQueue(tmp_path/'queue');session=str(uuid4());q.connect(session)
    papers=[{'request_id':str(uuid4()),'doi':f'10.1287/test.{i}','output_dir':str(tmp_path/f'out{i}')} for i in range(2)]
    q.submit(papers[0]['doi'],tmp_path,payload={'experiment':'parallel_batch','papers':papers,'concurrency':2},ttl=1545)
    record=q.claim(session);assert record['expires']-record['created']==1545
    inbox=queue.Queue();sent=[]
    def msg(kind,**fields):return {'v':1,'type':kind,'session_id':session,'request_id':record['request_id'],**fields}
    if race=='after_seal':inbox.put(msg('paper_failed',paper_id=papers[1]['request_id'],reason='no access'))
    inbox.put(msg('batch_candidate',download_id=0,path='/tmp/0.pdf'))
    if race=='late_failure':inbox.put(msg('paper_failed',paper_id=papers[0]['request_id'],reason='timeout'))
    if race!='after_seal':inbox.put(msg('batch_candidate',download_id=1,path='/tmp/1.pdf'))
    class Pool:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def submit(self,fn,message,*args):
            f=Future();f.set_result((papers[message['download_id']]['request_id'],{'status':'verified_fulltext','reason':'verified'}));return f
    monkeypatch.setattr(batch,'ThreadPoolExecutor',Pool)
    transition=q.transition
    def racing_transition(rid,owner,expected,status,payload):
        if race=='cancel' and status=='verified_fulltext':q.cancel(rid)
        return transition(rid,owner,expected,status,payload)
    monkeypatch.setattr(q,'transition',racing_transition)
    def send(kind,**fields):
        sent.append((kind,fields))
        if kind=='seal_batch':
            if race=='after_seal':inbox.put(msg('batch_candidate',download_id=1,path='/tmp/1.pdf'))
            inbox.put(msg('batch_closed',download_ids=[0] if race=='after_seal' else [0,1]))
    run_batch(record,session,{'data_dir':str(tmp_path)},q,inbox,send)
    final=q.get(record['request_id']);report=next(fields for kind,fields in sent if kind=='batch_result')
    assert report['status']==final['state']
    assert final['state']==('cancelled' if race=='cancel' else 'needs_attention')
    if race=='late_failure':assert final['payload']['results'][papers[0]['request_id']]['status']=='needs_attention'
    if race=='after_seal':assert final['payload']['reason']=='candidate_after_seal'


def test_real_host_batch_reversed_pdfs_and_independent_failure(tmp_path):
    import json,subprocess,sys
    from pathlib import Path
    from paper_access.bridge.protocol import read_message,write_message
    fixture_dir=Path(os.environ.get('PAPER_ACCESS_ACCEPTANCE_DIR','/__paper_access_fixture_missing__'))
    samples=[fixture_dir/'EBSCO-FullText-09_30_2026 (2).pdf',fixture_dir/'EBSCO-FullText-09_30_2026 (3).pdf']
    if not all(p.exists() for p in samples):pytest.skip('local acceptance samples absent')
    data=tmp_path/'data';data.mkdir();downloads=tmp_path/'downloads';downloads.mkdir()
    for i,p in enumerate(samples):(downloads/f'{i}.pdf').write_bytes(p.read_bytes())
    config=tmp_path/'config.json';config.write_text(json.dumps({'extension_id':'a'*32,'data_dir':str(data),'download_root':str(downloads)}))
    process=subprocess.Popen([sys.executable,'-m','paper_access.bridge.host',str(config),'chrome-extension://'+'a'*32+'/'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        hello=read_message(process.stdout);write_message(process.stdin,hello);session=hello['session_id']
        q=BridgeQueue(data/'bridge.sqlite3')
        papers=[{'request_id':str(uuid4()),'doi':doi,'output_dir':str(tmp_path/f'out{i}')} for i,doi in enumerate(['10.1287/mnsc.2018.3148','10.1287/msom.2019.0800','10.1287/test.failure'])]
        r=q.submit(papers[0]['doi'],tmp_path,payload={'experiment':'parallel_batch','papers':papers,'concurrency':3})
        assert read_message(process.stdout)['type']=='start_batch'
        def send(kind,**fields):write_message(process.stdin,dict(v=1,type=kind,session_id=session,request_id=r['request_id'],**fields))
        send('paper_failed',paper_id=papers[2]['request_id'],reason='test_unavailable')
        for i in [1,0]:send('batch_candidate',download_id=i,path=str(downloads/f'{i}.pdf'))
        notifications=[]
        while True:
            result=read_message(process.stdout);notifications.append(result)
            if result['type']=='seal_batch':send('batch_closed',download_ids=[1,0])
            if result['type']=='batch_result':break
        assert result['status']=='needs_attention' and result['reason']=='partial_failure',result
        assert len([m for m in notifications if m['type']=='paper_result'])==3
        children=q.get(r['request_id'])['payload']['results']
        assert all(children[p['request_id']]['status']=='verified_fulltext' for p in papers[:2])
        assert children[papers[2]['request_id']]['reason']=='test_unavailable'
        assert all(list((Path(p['output_dir'])/'files').glob('*.pdf')) for p in papers[:2])
    finally:
        process.stdin.close();process.wait(timeout=15)
        assert process.returncode==0,process.stderr.read().decode()
