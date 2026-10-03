import io
from uuid import uuid4
import pytest
from paper_access.bridge.host import serve
from paper_access.bridge.queue import BridgeQueue
from paper_access.bridge.protocol import write_message,read_message


def test_host_rejects_origin(tmp_path):
    q=BridgeQueue(tmp_path/'q')
    with pytest.raises(ValueError):serve(io.BytesIO(),io.BytesIO(),'chrome-extension://bad/',{'extension_id':'a'*32,'data_dir':str(tmp_path)},q)


def test_host_handshake_and_eof(tmp_path):
    q=BridgeQueue(tmp_path/'q');out=io.BytesIO()
    assert serve(io.BytesIO(),out,'chrome-extension://'+'a'*32+'/',{'extension_id':'a'*32,'data_dir':str(tmp_path)},q)==0
    out.seek(0);assert read_message(out)['type']=='hello'
    assert not q.connected()
