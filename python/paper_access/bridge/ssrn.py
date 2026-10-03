"""Independent SSRN file adapter; never infer a published version from its host."""
from pathlib import Path
from .protocol import valid_ssrn_id
from .validation import stage_candidate
from ..models import PaperInput, SourceRef, JobOptions
from ..institution import import_file
from ..ssrn_identity import clean_title

def validate_ssrn_candidate(request,candidate,config,store):
    identifier=valid_ssrn_id(request['doi'])
    if candidate['ssrn_id']!=identifier:
        return {'status':'needs_attention','reason':'ssrn_request_identity_mismatch'}
    staged=stage_candidate(candidate['path'],Path(config['download_root']),Path(config['data_dir'])/'bridge-staging')
    try:
        paper=PaperInput('ssrn',identifier,(SourceRef('ssrn-browser',1,'https://papers.ssrn.com/sol3/papers.cfm?abstract_id='+identifier),),clean_title(candidate['title']),tuple(candidate['authors']))
        job=store.create([paper],[],JobOptions(Path(request['output_dir']),version_policy=request.get('version_policy','best-available'),validation_policy=request.get('validation_policy','advisory')))
        code=import_file(job,paper.paper_id,staged,store,version='unknown',version_evidence='Downloaded through SSRN normal browser link; publication version not established')
        snapshot=store.snapshot(job)
        from .delivery import delivery_result
        result=delivery_result(job,store)
        return {**result,'version':'unknown','source':'ssrn-browser'}
    finally:staged.unlink(missing_ok=True)
