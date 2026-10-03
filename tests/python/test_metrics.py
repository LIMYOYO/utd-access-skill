from paper_access.benchmark import summarize_job
from paper_access.models import JobOptions, ImportIssue
from paper_access.store import JobStore


def test_metrics_keep_invalid_input_in_denominator(tmp_path, expected_paper):
    store = JobStore(tmp_path / "db")
    job = store.create([expected_paper], [ImportIssue("in",2,"bad","invalid identifier")], JobOptions(tmp_path / "out"))
    result = summarize_job(job, store)
    assert result["total_inputs"] == 2
    assert result["verified"] == 0 and result["coverage"] == 0
    assert result["invalid_inputs"] == 1
    assert result["request_latency_seconds"] is None
    assert result["cost_complete"] is False


def test_metrics_include_persisted_request_latency(tmp_path, expected_paper):
    store=JobStore(tmp_path/"db")
    job=store.create([expected_paper],[],JobOptions(tmp_path/"out"))
    store.record_request_event(job,{"provider":"fixture","elapsed_seconds":0.25,"status_code":200,"error":None})
    result=summarize_job(job,store)
    assert result["request_latency_seconds"]=={"count":1,"p50":0.25,"p95":0.25}
