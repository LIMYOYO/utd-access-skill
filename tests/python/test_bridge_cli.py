from paper_access.bridge.cli import execute

def test_fetch_without_connection_does_not_queue(tmp_path):
    code,result=execute(['fetch','10.1287/a','--out',str(tmp_path/'out')],data_dir=tmp_path)
    assert code!=0
    assert result['reason']=='bridge_unavailable'
