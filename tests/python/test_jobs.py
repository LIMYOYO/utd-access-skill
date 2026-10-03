from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path
import sqlite3

import pytest

from paper_access.imports import import_records
from paper_access.models import AttemptOutcome, JobOptions
from paper_access.store import JobStore, JobBusy


def new_job(tmp_path):
    source = tmp_path / "papers.txt"
    source.write_text("10.1234/one\nhttps://doi.org/10.1234/one\n10.bad/nope\n10.1234/two\n")
    papers, issues = import_records(source)
    options = JobOptions(output_dir=tmp_path / "output")
    store = JobStore(tmp_path / "state.sqlite")
    job = store.create(papers, issues, options)
    return store, job, papers


def test_job_persists_original_inputs_and_immutable_options(tmp_path):
    store, job, papers = new_job(tmp_path)
    restored = JobStore(tmp_path / "state.sqlite")
    snapshot = restored.snapshot(job)
    assert snapshot["input_count"] == 4
    assert len(snapshot["papers"]) == 2
    assert len(snapshot["issues"]) == 1
    assert [s["line"] for s in snapshot["papers"][0]["sources"]] == [1, 2]
    assert [p.paper_id for p in restored.pending(job)] == [p.paper_id for p in papers]
    assert restored.options(job).max_cost_usd == Decimal("0")
    with pytest.raises(FrozenInstanceError):
        restored.options(job).max_cost_usd = Decimal("9")


@pytest.mark.parametrize("value", ["-1", "NaN", "Infinity"])
def test_invalid_budget_rejected(value, tmp_path):
    with pytest.raises(ValueError):
        JobOptions(output_dir=tmp_path, max_cost_usd=Decimal(value))


def test_attempts_and_retry_due_time_survive_reopen(tmp_path):
    store, job, papers = new_job(tmp_path)
    store.record_attempt(job, papers[0].paper_id, AttemptOutcome("rate_limited", "repository", "http_429", next_retry_at=100))
    assert [p.paper_id for p in store.pending(job, now=99)] == [papers[1].paper_id]
    assert len(store.pending(job, now=101)) == 2
    snapshot = JobStore(tmp_path / "state.sqlite").snapshot(job)
    assert snapshot["papers"][0]["status"] == "rate_limited"
    assert snapshot["attempts"][0]["cost_usd"] is None


def test_success_cannot_be_recorded_as_attempt_without_verified_artifact(tmp_path):
    store, job, papers = new_job(tmp_path)
    with pytest.raises(ValueError, match="artifact"):
        store.record_attempt(job, papers[0].paper_id, AttemptOutcome("verified_fulltext", "repo", "ok"))
    assert store.snapshot(job)["papers"][0]["status"] == "queued"


def test_foreign_paper_attempt_rolls_back(tmp_path):
    store, job, _ = new_job(tmp_path)
    with pytest.raises(KeyError):
        store.record_attempt(job, "unknown", AttemptOutcome("not_found", "repo", "no_candidate"))
    assert not store.snapshot(job)["attempts"]


def test_second_database_connection_cannot_take_live_job_lease(tmp_path):
    store, job, _ = new_job(tmp_path)
    other = JobStore(tmp_path / "state.sqlite")
    owner = store.acquire_lease(job, now=10, ttl=20)
    with pytest.raises(JobBusy):
        other.acquire_lease(job, now=11, ttl=20)
    successor = other.acquire_lease(job, now=31, ttl=20)
    assert successor != owner
    store.release_lease(job, owner)
    with pytest.raises(JobBusy):
        store.acquire_lease(job, now=32)
    other.release_lease(job, successor)
    assert store.acquire_lease(job, now=33)


def test_lease_renewal_and_expired_owner_cannot_renew(tmp_path):
    store, job, _ = new_job(tmp_path)
    owner = store.acquire_lease(job, now=10, ttl=10)
    store.renew_lease(job, owner, now=15, ttl=10)
    with pytest.raises(JobBusy):
        JobStore(tmp_path / "state.sqlite").acquire_lease(job, now=21)
    with pytest.raises(JobBusy):
        store.renew_lease(job, owner, now=26)


def test_future_schema_is_not_silently_downgraded(tmp_path):
    db = tmp_path / "future.sqlite"
    with sqlite3.connect(db) as connection:
        connection.execute("PRAGMA user_version=999")
    with pytest.raises(ValueError, match="schema"):
        JobStore(db)


def test_artifact_registration_is_idempotent_without_claiming_verification(tmp_path):
    from paper_access.models import Artifact

    store, job, papers = new_job(tmp_path)
    file = tmp_path / "paper.pdf"
    file.write_bytes(b"unverified bytes")
    artifact = Artifact(path=file, sha256="a" * 64, mime_type="application/pdf", byte_count=16)
    store.record_artifact(job, papers[0].paper_id, artifact)
    store.record_artifact(job, papers[0].paper_id, artifact)
    snapshot = store.snapshot(job)
    assert len(snapshot["artifacts"]) == 1
    assert snapshot["verified_count"] == 0
