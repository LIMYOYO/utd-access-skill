import asyncio
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from paper_access.budget import BudgetLedger
from paper_access.config import CredentialResolver
from paper_access.http import HttpClient
from paper_access.models import JobOptions
from paper_access.providers.base import AccessContext
from paper_access.providers.openalex import OpenAlex
from paper_access.runner import run_job
from paper_access.store import JobStore, JobBusy


async def public(host):
    return ["93.184.216.34"]


def setup(tmp_path, expected_paper, pdf_file, *, policy="best-available", purpose="reading", bad_file=False):
    store = JobStore(tmp_path / "jobs.sqlite")
    options = JobOptions(tmp_path / "out", version_policy=policy, purpose=purpose)
    job = store.create([expected_paper], [], options)
    payload = pdf_file().path.read_bytes() if not bad_file else b'<html><input type="password">Sign in</html>'
    calls = []
    def respond(request):
        calls.append(request.url.path)
        if request.headers["host"] == "api.openalex.org":
            return httpx.Response(200, json={"doi": "https://doi.org/10.1234/queues", "locations": [{"id": "repo:one", "is_oa": True,
                "pdf_url": "https://repo.example/file.pdf", "version": "acceptedVersion", "license": "cc-by"}]})
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=payload)
    async def run():
        async with HttpClient(transport=httpx.MockTransport(respond), resolver=public) as http:
            return await run_job(job, store, AccessContext(http, BudgetLedger(store), CredentialResolver(), options, job), providers=[OpenAlex()])
    return store, job, calls, run


def test_fetch_then_resume_reuses_verified_file_without_network(tmp_path, expected_paper, pdf_file):
    store, job, calls, run = setup(tmp_path, expected_paper, pdf_file)
    assert asyncio.run(run()) == 0
    snapshot = store.snapshot(job)
    assert snapshot["verified_count"] == 1
    assert Path(snapshot["artifacts"][0]["path"]).is_file()
    calls.clear()
    assert asyncio.run(run()) == 0
    assert calls == []
    assert len(store.snapshot(job)["artifacts"]) == 1
    assert (tmp_path / "out" / "report.html").exists()


def test_failed_download_does_not_accumulate_partial_files(tmp_path, expected_paper, pdf_file):
    store, job, calls, run = setup(tmp_path, expected_paper, pdf_file, bad_file=True)
    for _ in range(3):
        assert asyncio.run(run()) == 2
        assert not list((tmp_path / "out" / ".partial").rglob("*.part"))
    assert store.snapshot(job)["artifacts"] == []


def test_rename_before_database_commit_recovers_without_second_download(tmp_path, expected_paper, pdf_file, monkeypatch):
    import paper_access.store as module
    store, job, calls, run = setup(tmp_path, expected_paper, pdf_file)
    original = module.os.replace
    class SimulatedCrash(BaseException):
        pass
    def crash_after_move(source, target):
        original(source, target)
        if str(source).endswith(".part"):
            raise SimulatedCrash()
    monkeypatch.setattr(module.os, "replace", crash_after_move)
    with pytest.raises(SimulatedCrash):
        asyncio.run(run())
    assert store.snapshot(job)["verified_count"] == 0
    monkeypatch.setattr(module.os, "replace", original)
    calls.clear()
    assert asyncio.run(run()) == 0
    assert calls == []
    assert store.snapshot(job)["verified_count"] == 1
    assert list((tmp_path / "out" / "text").glob("*.json"))


def test_login_page_never_counts_as_fulltext(tmp_path, expected_paper, pdf_file):
    store, job, _, run = setup(tmp_path, expected_paper, pdf_file, bad_file=True)
    assert asyncio.run(run()) == 2
    assert store.snapshot(job)["verified_count"] == 0
    assert not list((tmp_path / "out" / "files").glob("*"))


def test_published_only_does_not_fetch_author_manuscript(tmp_path, expected_paper, pdf_file):
    store, job, calls, run = setup(tmp_path, expected_paper, pdf_file, policy="published-only")
    assert asyncio.run(run()) == 2
    assert "/file.pdf" not in calls
    assert store.snapshot(job)["verified_count"] == 0


def test_ai_purpose_requires_explicit_source_capability(tmp_path, expected_paper, pdf_file):
    store, job, calls, run = setup(tmp_path, expected_paper, pdf_file, purpose="ai")
    assert asyncio.run(run()) == 2
    assert "/file.pdf" not in calls
    assert store.snapshot(job)["papers"][0]["status"] == "needs_rights_review"


def test_missing_verified_file_is_reacquired(tmp_path, expected_paper, pdf_file):
    store, job, calls, run = setup(tmp_path, expected_paper, pdf_file)
    assert asyncio.run(run()) == 0
    Path(store.snapshot(job)["artifacts"][0]["path"]).unlink()
    calls.clear()
    assert asyncio.run(run()) == 0
    assert "/file.pdf" in calls


def test_active_job_lease_prevents_second_runner(tmp_path, expected_paper, pdf_file):
    store, job, calls, run = setup(tmp_path, expected_paper, pdf_file)
    owner = store.acquire_lease(job)
    with pytest.raises(JobBusy):
        asyncio.run(run())
    assert calls == []
    store.release_lease(job, owner)


def test_report_contains_download_path_and_version(tmp_path, expected_paper, pdf_file):
    import json
    store, job, _, run = setup(tmp_path, expected_paper, pdf_file)
    assert asyncio.run(run()) == 0
    row = json.loads((tmp_path / "out" / "manifest.jsonl").read_text().splitlines()[0])
    assert row["version"] == "acceptedVersion"
    assert row["file"].startswith("files/")
    assert (tmp_path / "out" / row["file"]).is_file()
    assert row["extraction_quality"] == "text_extracted_layout_unverified"


def test_staged_part_survives_crash_before_rename_without_redownload(tmp_path, expected_paper, pdf_file, monkeypatch):
    store, job, calls, run = setup(tmp_path, expected_paper, pdf_file)
    original = store.publish_artifact
    def crash(*args, **kwargs):
        raise RuntimeError("simulated before rename")
    monkeypatch.setattr(store, "publish_artifact", crash)
    with pytest.raises(RuntimeError):
        asyncio.run(run())
    monkeypatch.setattr(store, "publish_artifact", original)
    calls.clear()
    assert asyncio.run(run()) == 0
    assert calls == []
    assert not list((tmp_path / "out" / ".partial").rglob("*.part"))


def test_failed_heartbeat_releases_lease_and_writes_report(tmp_path, expected_paper, monkeypatch):
    import paper_access.runner as module
    store = JobStore(tmp_path / "db")
    options = JobOptions(tmp_path / "out")
    job = store.create([expected_paper], [], options)
    async def scenario():
        entered = asyncio.Event()
        original_sleep = asyncio.sleep
        original_renew = store.renew_lease
        async def sleep(delay):
            if delay == 30:
                await entered.wait()
            else:
                await original_sleep(delay)
        def renew(*args, **kwargs):
            if entered.is_set():
                raise JobBusy("simulated heartbeat failure")
            return original_renew(*args, **kwargs)
        async def respond(request):
            entered.set()
            await asyncio.Event().wait()
        monkeypatch.setattr(module.asyncio, "sleep", sleep)
        monkeypatch.setattr(store, "renew_lease", renew)
        async with HttpClient(transport=httpx.MockTransport(respond), resolver=public) as http:
            ctx = AccessContext(http, BudgetLedger(store), CredentialResolver(), options, job)
            with pytest.raises(JobBusy, match="heartbeat"):
                await run_job(job, store, ctx, providers=[OpenAlex()])
    asyncio.run(scenario())
    with store.connection() as db:
        assert db.execute("SELECT lease_owner FROM jobs WHERE job_id=?", (job,)).fetchone()[0] is None
    assert (tmp_path / "out" / "report.html").is_file()


def test_resume_report_uses_revalidated_file_not_stale_artifact(tmp_path, expected_paper, pdf_file, candidate):
    import json
    from paper_access.validate import validate_artifact
    store, job, calls, run = setup(tmp_path, expected_paper, pdf_file)
    assert asyncio.run(run()) == 0
    original = store.snapshot(job)["artifacts"][0]
    stale = pdf_file(name="stale.pdf", body=["Other text from the same article. " * 10] * 10)
    for index in range(1000):
        if stale.sha256 > original["sha256"]:
            break
        stale = pdf_file(name="stale.pdf", body=[f"Variation {index} of main article text. " * 10] * 10)
    assert stale.sha256 > original["sha256"]
    stale = replace(stale, path=tmp_path / "out" / "files" / "stale.pdf")
    stale.path.write_bytes((tmp_path / "stale.pdf").read_bytes())
    owner = store.acquire_lease(job)
    store.stage_artifact(job, expected_paper.paper_id, stale, candidate, validate_artifact(stale, expected_paper, candidate), owner)
    store.publish_artifact(job, expected_paper.paper_id, stale.sha256, owner)
    store.release_lease(job, owner)
    stale.path.unlink()
    calls.clear()
    assert asyncio.run(run()) == 0
    assert calls == []
    row = json.loads((tmp_path / "out" / "manifest.jsonl").read_text().splitlines()[0])
    assert (tmp_path / "out" / row["file"]).resolve() == Path(original["path"]).resolve()


def test_legacy_report_retains_revalidated_file_without_resume(tmp_path, expected_paper, pdf_file):
    import json
    from paper_access.report import write_report
    store, job, _, run = setup(tmp_path, expected_paper, pdf_file)
    assert asyncio.run(run()) == 0
    with store.connection() as db:
        for row in db.execute("SELECT sha256,data FROM artifacts WHERE job_id=?", (job,)).fetchall():
            data = json.loads(row["data"])
            data.pop("active")
            db.execute("UPDATE artifacts SET data=? WHERE job_id=? AND sha256=?", (json.dumps(data), job, row["sha256"]))
    write_report(job, store, tmp_path / "out")
    row = json.loads((tmp_path / "out" / "manifest.jsonl").read_text().splitlines()[0])
    assert row["file"]
    assert (tmp_path / "out" / row["file"]).is_file()
    assert row["version"] == "acceptedVersion"


def test_discovery_backoff_is_not_overwritten_by_no_candidate(tmp_path, expected_paper):
    import time
    from paper_access.models import AttemptOutcome
    from paper_access.providers.base import ProviderFailure
    store=JobStore(tmp_path/"db");options=JobOptions(tmp_path/"out");job=store.create([expected_paper],[],options)
    deadline=time.time()+3600
    class Limited:
        async def discover(self,paper,context):raise ProviderFailure(AttemptOutcome("rate_limited","fixture","cooldown",next_retry_at=deadline))
    class Missing:
        async def discover(self,paper,context):raise ProviderFailure(AttemptOutcome("needs_credentials","other","missing_key"))
    async def run():
        async with HttpClient(transport=httpx.MockTransport(lambda r: httpx.Response(500)),resolver=public) as http:
            return await run_job(job,store,AccessContext(http,BudgetLedger(store),CredentialResolver(),options,job),providers=[Limited(),Missing()])
    assert asyncio.run(run())==2
    paper=store.snapshot(job)["papers"][0]
    assert paper["status"]=="rate_limited" and paper["next_retry_at"]==deadline
    assert store.pending(job)==[]
