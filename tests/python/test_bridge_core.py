import io
import struct
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from paper_access.bridge.protocol import read_message, write_message, validate_message
from paper_access.bridge.queue import BridgeQueue


def test_frames():
    s=io.BytesIO();write_message(s,{"v":1,"type":"hello","session_id":str(uuid4())});s.seek(0)
    assert read_message(s)["type"]=="hello"
    assert read_message(s) is None
    with pytest.raises(ValueError):read_message(io.BytesIO(struct.pack("=I",65537)))
    with pytest.raises(ValueError):read_message(io.BytesIO(struct.pack("=I",10)+b"{}"))
    with pytest.raises(ValueError):validate_message({"v":1,"type":"start","session_id":str(uuid4()),"request_id":"bad","doi":"10.1287/foo"},"host")


def test_queue_single_claim_cancel(tmp_path):
    q=BridgeQueue(tmp_path/'bridge.sqlite3');r=q.submit('10.1287/mnsc.2018.3061',tmp_path/'out',100)
    with pytest.raises(ValueError):q.submit('10.1287/msom.2019.0800',tmp_path/'out',100)
    with ThreadPoolExecutor(2) as pool:
        claims=list(pool.map(lambda _:q.claim(str(uuid4()),101),range(2)))
    assert sum(x is not None for x in claims)==1
    owner=next(x for x in claims if x)['session_id']
    assert not q.transition(r['request_id'],str(uuid4()),('dispatched',),'downloading',{})
    q.cancel(r['request_id'])
    assert not q.transition(r['request_id'],owner,('dispatched',),'verified_fulltext',{})
    assert q.get(r['request_id'])['state']=='cancelled'


def test_disconnect_never_requeues(tmp_path):
    q=BridgeQueue(tmp_path/'q');r=q.submit('10.1287/a',tmp_path,100);session=str(uuid4());q.claim(session,101)
    q.disconnect(session)
    assert q.get(r['request_id'])['state']=='needs_attention'
    assert q.claim(str(uuid4()),102) is None


def test_expiry(tmp_path):
    q=BridgeQueue(tmp_path/'q');r=q.submit('10.1287/a',tmp_path,100)
    assert q.claim(str(uuid4()),401) is None
    assert q.get(r['request_id'])['state']=='failed'


def test_reconnect_preserves_candidate_for_validation(tmp_path):
    q=BridgeQueue(tmp_path/'q');r=q.submit('10.1287/a',tmp_path,100);old=str(uuid4());q.claim(old,101)
    q.transition(r['request_id'],old,('dispatched',),'verifying',{'candidate':{'path':'/tmp/a.pdf'}})
    q.connect(str(uuid4()))
    assert q.get(r['request_id'])['state']=='downloaded_unverified'
    assert q.get(r['request_id'])['payload']['candidate']['path']=='/tmp/a.pdf'
