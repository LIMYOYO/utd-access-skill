import csv
import json
from decimal import Decimal

from paper_access.cli import main
from paper_access.imports import import_records
from paper_access.models import JobOptions
from paper_access.report import write_report
from paper_access.store import JobStore
from paper_access.models import AttemptOutcome


def test_reports_keep_invalid_inputs_and_escape_external_titles(tmp_path):
    path = tmp_path / "papers.csv"
    path.write_text('doi,title\n10.1234/one,<script>alert(1)</script>\n10.bad/nope,Invalid\n,=1+2\n')
    papers, issues = import_records(path)
    store = JobStore(tmp_path / "state.sqlite")
    output = tmp_path / "out"
    job = store.create(papers, issues, JobOptions(output_dir=output))
    write_report(job, store, output)
    html = (output / "report.html").read_text()
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "invalid_input" in html
    manifest = [json.loads(line) for line in (output / "manifest.jsonl").read_text().splitlines()]
    assert len(manifest) == 3
    with (output / "report.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 3
    assert rows[2]["title"] == "'=1+2"
    assert rows[0]["cost_usd"] == ""
    assert (output / "pending.csv").exists()
    assert (output / "pending.html").exists()


def test_plan_and_report_cli_persist_across_invocations(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PAPER_ACCESS_DATA_DIR", str(tmp_path / "state"))
    source = tmp_path / "papers.txt"
    source.write_text("10.1234/one\n10.bad/broken\n")
    assert main(["plan", str(source), "--out", str(tmp_path / "out"), "--version", "published-only", "--max-cost-usd", "0"]) == 0
    planned = json.loads(capsys.readouterr().out)
    assert planned["input_count"] == 2
    assert planned["options"]["version_policy"] == "published-only"
    assert main(["report", planned["job_id"], "--format", "json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["verified_count"] == 0
    assert len(report["papers"]) == 1 and len(report["issues"]) == 1
    assert not list((tmp_path / "out").glob("files/*"))


def test_cli_fatal_error_has_nonzero_exit_and_no_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PAPER_ACCESS_DATA_DIR", str(tmp_path / "state"))
    assert main(["plan", str(tmp_path / "missing.bib"), "--out", str(tmp_path / "out")]) == 1
    assert "Traceback" not in capsys.readouterr().err


def test_report_retains_source_failures_before_optional_credential_failure(tmp_path, expected_paper):
    store = JobStore(tmp_path / "db")
    output = tmp_path / "out"
    job = store.create([expected_paper], [], JobOptions(output))
    store.record_attempt(job, expected_paper.paper_id, AttemptOutcome("downloaded_unverified", "repository", "not_fulltext"))
    store.record_attempt(job, expected_paper.paper_id, AttemptOutcome("needs_credentials", "openalex", "missing_api_key"))
    write_report(job, store, output)
    row = json.loads((output / "manifest.jsonl").read_text())
    assert [item["reason_code"] for item in row["attempts"]] == ["not_fulltext", "missing_api_key"]
    with (output / "report.csv").open() as stream:
        assert len(json.loads(next(csv.DictReader(stream))["attempts"])) == 2
    html = (output / "pending.html").read_text()
    assert "not_fulltext" in html and "missing_api_key" in html


def test_report_preserves_known_cost_and_unknown_cost_separately(tmp_path, expected_paper):
    store = JobStore(tmp_path / "db")
    output = tmp_path / "out"
    job = store.create([expected_paper], [], JobOptions(output))
    store.record_attempt(job, expected_paper.paper_id, AttemptOutcome("downloaded_unverified", "openalex", "invalid_document", cost_usd=Decimal("0.01"), redacted_detail="charged invalid document"))
    store.record_attempt(job, expected_paper.paper_id, AttemptOutcome("not_found", "repository", "http_404", cost_usd=Decimal("0")))
    write_report(job, store, output)
    row = json.loads((output / "manifest.jsonl").read_text())
    assert row["cost_usd"] == "0.01"
    assert row["attempts"][0]["redacted_detail"] == "charged invalid document"
    assert row["attempts"][0]["cost_usd"] == "0.01"
    assert row["attempts"][0]["created_at"] > 0
    store.record_attempt(job, expected_paper.paper_id, AttemptOutcome("retryable_failure", "openalex", "unknown_charge"))
    write_report(job, store, output)
    row = json.loads((output / "manifest.jsonl").read_text())
    assert row["cost_usd"] is None
    assert row["known_cost_usd"] == "0.01"
    assert row["cost_complete"] is False
