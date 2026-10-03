"""Provider-neutral result for the independent download and identity gates."""
from pathlib import Path

def delivery_result(job, store):
    snapshot=store.snapshot(job)
    artifacts=[a for a in snapshot['artifacts'] if a.get('active')]
    artifact=artifacts[0] if artifacts else None
    usable=artifact is not None and artifact['validation']['status'] in {'verified_fulltext','downloaded_fulltext'}
    verified=usable and artifact['validation']['status']=='verified_fulltext'
    reason=artifact['validation']['reason_code'] if usable else snapshot['attempts'][-1]['reason_code']
    allowed=usable and (verified or store.options(job).validation_policy=='advisory')
    identity='verified' if verified else 'authors_blinded' if reason=='anonymous_authors_unverified' else 'not_verified'
    return {'status':'verified_fulltext' if verified else 'downloaded_fulltext' if allowed else 'needs_attention',
            'reason':reason, 'identity_reason':reason, 'download_status':'complete' if usable else 'not_complete',
            'identity_status':identity, 'analysis_allowed':allowed,
            'message':'正文已下载，身份核对通过' if verified else '正文已下载；身份待核对，允许继续分析' if allowed else '正文已下载；严格模式要求身份核对通过' if usable else '未取得可用正文：'+reason,
            'delivered_file':artifact['path'] if usable else None,
            'version':artifact['version'] if usable else 'unknown','job_id':job,'report':str(store.options(job).output_dir/'report.json'), 'snapshot':snapshot}
