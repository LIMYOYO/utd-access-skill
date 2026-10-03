from pathlib import Path
from uuid import uuid4
import os
import pytest
from paper_access.bridge.pair import identify_candidate
from paper_access.bridge.protocol import validate_message


def test_pair_protocol_distinct_two_papers():
    message={'v':1,'type':'start_pair','session_id':str(uuid4()),'request_id':str(uuid4()),'papers':[{'request_id':str(uuid4()),'doi':'10.1287/a'},{'request_id':str(uuid4()),'doi':'10.1287/b'}]}
    assert validate_message(message,'host')==message
    message['papers'][1]['doi']='10.1287/a'
    with pytest.raises(ValueError):validate_message(message,'host')


def test_candidate_matches_primary_doi_not_arrival_order(tmp_path):
    sample=Path(os.environ.get('PAPER_ACCESS_ACCEPTANCE_DIR','/__paper_access_fixture_missing__'))/'EBSCO-FullText-09_30_2026 (1).pdf'
    if not sample.exists():pytest.skip('local acceptance sample absent')
    papers=[{'request_id':'other','doi':'10.1287/msom.2019.0800'},{'request_id':'correct','doi':'10.1287/mnsc.2018.3061'}]
    assert identify_candidate(sample,papers)=='correct'
    with pytest.raises(ValueError):identify_candidate(sample,papers[:1])


def test_real_host_pair_reversed_candidates(tmp_path):
    import json,subprocess,sys
    from paper_access.bridge.queue import BridgeQueue
    from paper_access.bridge.protocol import read_message,write_message
    fixture_dir=Path(os.environ.get('PAPER_ACCESS_ACCEPTANCE_DIR','/__paper_access_fixture_missing__'))
    samples=[fixture_dir/'EBSCO-FullText-09_30_2026 (2).pdf',fixture_dir/'EBSCO-FullText-09_30_2026 (3).pdf']
    if not all(p.exists() for p in samples):pytest.skip('local samples absent')
    data=tmp_path/'data';data.mkdir();downloads=tmp_path/'downloads';downloads.mkdir()
    for i,p in enumerate(samples):(downloads/f'{i}.pdf').write_bytes(p.read_bytes())
    config=tmp_path/'config.json';config.write_text(json.dumps({'extension_id':'a'*32,'data_dir':str(data),'download_root':str(downloads)}))
    process=subprocess.Popen([sys.executable,'-m','paper_access.bridge.host',str(config),'chrome-extension://'+'a'*32+'/'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        hello=read_message(process.stdout);write_message(process.stdin,hello);session=hello['session_id']
        q=BridgeQueue(data/'bridge.sqlite3')
        papers=[{'request_id':str(uuid4()),'doi':doi,'output_dir':str(tmp_path/f'out{i}')} for i,doi in enumerate(['10.1287/mnsc.2018.3148','10.1287/msom.2019.0800'])]
        r=q.submit(papers[0]['doi'],tmp_path,payload={'experiment':'parallel_pair','papers':papers})
        start=read_message(process.stdout);assert start['type']=='start_pair'
        for i in [1,0]:write_message(process.stdin,{'v':1,'type':'pool_candidate','session_id':session,'request_id':r['request_id'],'download_id':i,'path':str(downloads/f'{i}.pdf')})
        result=read_message(process.stdout)
        if result['type']=='seal_pair':
            write_message(process.stdin,{'v':1,'type':'pool_closed','session_id':session,'request_id':r['request_id'],'download_ids':[1,0]})
            result=read_message(process.stdout)
        if result['type']=='cancel':result=read_message(process.stdout)
        assert result['type']=='pair_result';assert result['status']=='verified_fulltext',result
        assert {x['request_id'] for x in result['results']}=={p['request_id'] for p in papers}
        assert all(list((Path(p['output_dir'])/'files').glob('*.pdf')) for p in papers)
    finally:
        process.stdin.close();process.wait(timeout=15)
        assert process.returncode==0,process.stderr.read().decode()


@pytest.mark.parametrize('late', ['third_candidate', 'error', 'close'])
def test_pair_waits_for_candidate_pool_close(monkeypatch,tmp_path,late):
    import queue,time
    from concurrent.futures import Future
    from paper_access.bridge import pair
    from paper_access.bridge.queue import BridgeQueue
    session=str(uuid4());q=BridgeQueue(tmp_path/'bridge.sqlite3');q.connect(session)
    papers=[{'request_id':str(uuid4()),'doi':'10.1287/'+x,'output_dir':str(tmp_path/x)} for x in ['a','b']]
    q.submit(papers[0]['doi'],tmp_path,payload={'papers':papers})
    record=q.claim(session);inbox=queue.Queue();sent=[]
    def event(kind,**fields):return dict(v=1,type=kind,session_id=session,request_id=record['request_id'],**fields)
    for i in [0,1]:inbox.put(event('pool_candidate',download_id=i,path=f'/tmp/{i}.pdf'))
    if late=='third_candidate':inbox.put(event('pool_candidate',download_id=2,path='/tmp/2.pdf'))
    if late=='error':inbox.put(event('error',reason='late_download_error'))
    class ImmediatePool:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def submit(self,fn,message,*args):
            f=Future();f.set_result((papers[message['download_id']]['request_id'],{'status':'verified_fulltext'}));return f
    monkeypatch.setattr(pair,'ThreadPoolExecutor',ImmediatePool)
    def send(kind,**fields):
        sent.append((kind,fields))
        if kind=='seal_pair':
            assert q.get(record['request_id'])['state']=='downloading'
            inbox.put(event('pool_closed',download_ids=[0,1]))
    pair.run_pair(record,session,{},q,inbox,send)
    result=q.get(record['request_id'])
    assert result['state']==('verified_fulltext' if late=='close' else 'needs_attention')
    if late=='close':assert any(kind=='seal_pair' for kind,_ in sent)
