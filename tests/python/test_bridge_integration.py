import json
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4
from paper_access.bridge.protocol import read_message,write_message
from paper_access.bridge.queue import BridgeQueue


def test_real_host_process_candidate_to_verified(tmp_path):
    # Use a previously acquired local acceptance file, never a network download.
    source=Path(os.environ.get('PAPER_ACCESS_ACCEPTANCE_DIR','/__paper_access_fixture_missing__'))/'EBSCO-FullText-09_30_2026 (1).pdf'
    if not source.exists():
        import pytest
        pytest.skip('local real-PDF acceptance sample is not available')
    data=tmp_path/'data';data.mkdir();downloads=tmp_path/'downloads';downloads.mkdir()
    pdf=downloads/'paper.pdf';pdf.write_bytes(source.read_bytes())
    config=tmp_path/'config.json';config.write_text(json.dumps({'extension_id':'a'*32,'data_dir':str(data),'download_root':str(downloads)}))
    process=subprocess.Popen([sys.executable,'-m','paper_access.bridge.host',str(config),'chrome-extension://'+'a'*32+'/'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        hello=read_message(process.stdout);session=hello['session_id']
        write_message(process.stdin,hello)
        q=BridgeQueue(data/'bridge.sqlite3');request=q.submit('10.1287/mnsc.2018.3061',tmp_path/'out')
        start=read_message(process.stdout);assert start['type']=='start';assert start['request_id']==request['request_id']
        write_message(process.stdin,{'v':1,'type':'candidate','session_id':session,'request_id':start['request_id'],'download_id':1,'path':str(pdf),'title':'Cournot Competition in Networked Markets','association':'candidate_no_referrer'})
        result=read_message(process.stdout);assert result['type']=='validation_result';assert result['status']=='verified_fulltext'
        assert q.get(start['request_id'])['state']=='verified_fulltext'
        assert list((tmp_path/'out'/'files').glob('*.pdf'))
    finally:
        process.stdin.close();process.wait(timeout=10)
        assert process.returncode==0,process.stderr.read().decode()
