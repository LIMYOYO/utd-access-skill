"""Exercise file delivery and report policy with generated, non-copyrighted PDFs."""
import json
from pathlib import Path

import pytest

from paper_access.bridge.delivery import delivery_result
from paper_access.bridge.ssrn import validate_ssrn_candidate
from paper_access.institution import import_file
from paper_access.models import JobOptions
from paper_access.store import JobStore


@pytest.mark.parametrize('policy,allowed', [('advisory', True), ('strict', False)])
def test_identity_failure_keeps_pdf_and_separates_analysis_gate(tmp_path, expected_paper, pdf_file, policy, allowed):
    store=JobStore(tmp_path/'jobs.sqlite3')
    out=tmp_path/'out'
    job=store.create([expected_paper],[],JobOptions(out,validation_policy=policy))
    source=pdf_file(author='Other Author')
    assert import_file(job,expected_paper.paper_id,source.path,store)==(0 if allowed else 2)
    result=delivery_result(job,store)
    assert result['download_status']=='complete'
    assert result['identity_status']=='not_verified'
    assert result['analysis_allowed'] is allowed
    assert Path(result['delivered_file']).is_file()
    row=json.loads(Path(result['report']).read_text())['rows'][0]
    assert row['download_status']=='complete'
    assert row['analysis_allowed'] is allowed


@pytest.mark.parametrize('policy', ['advisory', 'strict'])
def test_login_page_never_passes_download_gate(tmp_path, expected_paper, policy):
    store=JobStore(tmp_path/'jobs.sqlite3')
    job=store.create([expected_paper],[],JobOptions(tmp_path/'out',validation_policy=policy))
    source=tmp_path/'login.pdf';source.write_bytes(b'<html><input type="password"></html>')
    assert import_file(job,expected_paper.paper_id,source,store)==2
    result=delivery_result(job,store)
    assert result['download_status']=='not_complete'
    assert result['analysis_allowed'] is False
    assert result['delivered_file'] is None


@pytest.mark.parametrize('policy,allowed', [('advisory', True), ('strict', False)])
def test_ssrn_adapter_preserves_identity_unverified_fulltext(tmp_path, pdf_file, policy, allowed):
    source=pdf_file(author='Other Author')
    request={'doi':'10.2139/ssrn.12345','output_dir':str(tmp_path/'out'),'validation_policy':policy}
    candidate={'ssrn_id':'12345','path':str(source.path),'title':'Queueing and Service Systems','authors':['Jane Smith']}
    config={'download_root':str(tmp_path),'data_dir':str(tmp_path/'data')}
    result=validate_ssrn_candidate(request,candidate,config,JobStore(tmp_path/'jobs.sqlite3'))
    assert result['source']=='ssrn-browser'
    assert result['version']=='unknown'
    assert result['download_status']=='complete'
    assert result['identity_status']=='not_verified'
    assert result['analysis_allowed'] is allowed
    assert Path(result['delivered_file']).is_file()
