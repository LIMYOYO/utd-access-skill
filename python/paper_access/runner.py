"""Discover, fetch, validate and recover a persistent job."""

import asyncio
from dataclasses import replace, asdict
from decimal import Decimal
from pathlib import Path

from .extract import extract_text
from .models import Artifact, AttemptOutcome, Candidate, PaperInput, SourceRef
from .providers.base import AccessContext, ProviderFailure
from .providers.crossref import Crossref
from .providers.arxiv import Arxiv
from .providers.repec import Repec
from .providers.openalex import OpenAlex
from .providers.unpaywall import Unpaywall
from .providers.repository import Repository
from .report import write_report
from .store import JobStore
from .validate import assess_artifact, USABLE_STATUSES, analysis_allowed


def _paper(data: dict) -> PaperInput:
    return PaperInput(data["identifier_kind"], data["identifier"], tuple(SourceRef(**s) for s in data["sources"]),
                      data["title"], tuple(data["authors"]), data["year"], data.get("resolved_doi"))


def _allowed(candidate: Candidate, context: AccessContext) -> AttemptOutcome | None:
    if context.options.version_policy == "published-only" and candidate.version != "publishedVersion":
        return AttemptOutcome("not_found", candidate.provider, "version_policy_mismatch")
    if context.options.purpose not in candidate.usage:
        return AttemptOutcome("needs_rights_review", candidate.provider, "purpose_not_supported")
    return None


async def _extract(job_id, store, context, owner, artifact, paper_id, previous=None):
    if previous and previous.get("path") and Path(previous["path"]).is_file():
        return
    result = await asyncio.to_thread(extract_text, artifact, context.options.output_dir / "text")
    if isinstance(result, AttemptOutcome):
        info = {"quality": result.reason_code, "path": None}
    else:
        info = {"quality": "text_extracted_layout_unverified", "path": str(result)}
    store.record_extraction(job_id, paper_id, artifact.sha256, info, owner)


async def _recover(job_id: str, store: JobStore, context: AccessContext, owner: str) -> None:
    snapshot = store.snapshot(job_id)
    papers = {p["paper_id"]: p for p in snapshot["papers"]}
    restored = set()
    for data in sorted(snapshot["artifacts"], key=lambda item: not item.get("active", False)):
        if "candidate" not in data or data["paper_id"] in restored:
            continue
        artifact = Artifact(**{key: Path(data[key]) if key == "path" else data[key] for key in Artifact.__dataclass_fields__ if key in data})
        candidate_data = dict(data["candidate"])
        candidate_data["estimated_cost_usd"] = Decimal(candidate_data["estimated_cost_usd"])
        candidate_data["usage"] = tuple(candidate_data["usage"])
        candidate = Candidate(**candidate_data)
        source = artifact.path
        if not source.is_file() and data.get("temporary"):
            source = Path(data["temporary"])
        if _allowed(candidate, context) or not source.is_file():
            continue
        validation = await asyncio.to_thread(assess_artifact, replace(artifact, path=source), _paper(papers[data["paper_id"]]), candidate)
        if validation.status in USABLE_STATUSES:
            if data.get('validation') != asdict(validation):
                store.stage_artifact(job_id,data['paper_id'],artifact,candidate,validation,owner,temporary=source if source != artifact.path else None)
                if data.get('extraction'):
                    store.record_extraction(job_id,data['paper_id'],artifact.sha256,data['extraction'],owner)
            if papers[data["paper_id"]]["status"] != validation.status or not data.get("active") or data.get("validation") != asdict(validation):
                store.publish_artifact(job_id, data["paper_id"], artifact.sha256, owner, temporary=source if source != artifact.path else None)
            await _extract(job_id, store, context, owner, artifact, data["paper_id"], data.get("extraction"))
            restored.add(data["paper_id"])
    for paper_id, paper in papers.items():
        if paper["status"] in USABLE_STATUSES and paper_id not in restored:
            store.record_attempt(job_id, paper_id, AttemptOutcome("queued", "cache", "cached_file_missing_or_invalid"), owner=owner)


async def _process(job_id, store, context, owner, providers):
    await _recover(job_id, store, context, owner)
    for paper in store.pending(job_id):
        store.renew_lease(job_id, owner)
        if paper.identifier_kind == "title" and not paper.doi:
            try:
                paper = await Crossref().resolve_title(paper, context)
                store.update_paper(job_id, paper, owner)
            except ProviderFailure as error:
                store.record_attempt(job_id, paper.paper_id, error.outcome, owner=owner)
                continue
        if paper.doi and (not paper.title or not paper.authors):
            try:
                paper = await Crossref().lookup(paper, context)
                store.update_paper(job_id, paper, owner)
            except ProviderFailure as error:
                store.record_attempt(job_id, paper.paper_id, error.outcome, owner=owner)
        candidates = []
        discovery_failures = []
        for provider in providers:
            if isinstance(provider, Arxiv) and paper.identifier_kind == "arxiv":
                try:
                    paper = await provider.lookup(paper, context)
                    store.update_paper(job_id, paper, owner)
                except ProviderFailure as error:
                    discovery_failures.append(error.outcome)
                    continue
            try:
                candidates.extend(await provider.discover(paper, context))
            except ProviderFailure as error:
                discovery_failures.append(error.outcome)
        rank = {"publishedVersion": 0, "acceptedVersion": 1, "submittedVersion": 2, "unknown": 3}
        candidates.sort(key=lambda c: (rank.get(c.version, 3), c.estimated_cost_usd))
        if not candidates:
            priority = {"not_found": 0, "needs_credentials": 1, "needs_login": 2,
                        "retryable_failure": 3, "rate_limited": 4}
            discovery_failures.sort(key=lambda outcome: (priority.get(outcome.status, 1), outcome.next_retry_at or 0))
        for failure in discovery_failures:
            store.record_attempt(job_id, paper.paper_id, failure, owner=owner)
        if not candidates and not discovery_failures:
            store.record_attempt(job_id, paper.paper_id, AttemptOutcome("not_found", "discovery", "no_fulltext_candidate"), owner=owner)
        for index, candidate in enumerate(candidates):
            blocked = _allowed(candidate, context)
            if blocked:
                store.record_attempt(job_id, paper.paper_id, blocked, owner=owner)
                continue
            store.renew_lease(job_id, owner)
            temporary = context.options.output_dir / ".partial" / job_id / owner / f"{paper.paper_id}-{index}.part"
            artifact = await Repository().acquire(candidate, context, destination=temporary)
            if isinstance(artifact, AttemptOutcome):
                temporary.unlink(missing_ok=True)
                store.record_attempt(job_id, paper.paper_id, artifact, owner=owner)
                continue
            validation = await asyncio.to_thread(assess_artifact, artifact, paper, candidate)
            if validation.status not in USABLE_STATUSES:
                temporary.unlink(missing_ok=True)
                store.record_attempt(job_id, paper.paper_id, AttemptOutcome(validation.status, candidate.provider, validation.reason_code), owner=owner)
                continue
            extension = {"application/pdf": ".pdf", "application/xml": ".xml", "text/html": ".html"}[validation.mime_type]
            final = context.options.output_dir / "files" / f"{paper.paper_id}-{artifact.sha256[:16]}{extension}"
            completed = replace(artifact, path=final, pages=validation.pages, mime_type=validation.mime_type)
            store.stage_artifact(job_id, paper.paper_id, completed, candidate, validation, owner, temporary=temporary)
            store.publish_artifact(job_id, paper.paper_id, completed.sha256, owner, temporary=temporary)
            await _extract(job_id, store, context, owner, completed, paper.paper_id)
            if analysis_allowed(validation, context.options):
                break


async def run_job(job_id: str, store: JobStore, context: AccessContext, *, providers=None) -> int:
    if context.job_id != job_id or context.options != store.options(job_id):
        raise ValueError("runner context differs from immutable job options")
    owner = store.acquire_lease(job_id)
    previous_hook = context.http.event_hook
    context.http.event_hook = lambda event: store.record_request_event(job_id, event)
    async def heartbeat():
        while True:
            await asyncio.sleep(30)
            store.renew_lease(job_id, owner)
    pulse = asyncio.create_task(heartbeat())
    work = asyncio.create_task(_process(job_id, store, context, owner, providers if providers is not None else [OpenAlex(), Unpaywall(), Arxiv(), Repec()]))
    try:
        done, _ = await asyncio.wait({work, pulse}, return_when=asyncio.FIRST_COMPLETED)
        if pulse in done:
            await pulse
        await work
    finally:
        for task in (work, pulse):
            if not task.done():
                task.cancel()
        await asyncio.gather(work, pulse, return_exceptions=True)
        context.http.event_hook = previous_hook
        store.release_lease(job_id, owner)
        write_report(job_id, store, context.options.output_dir)
    snapshot = store.snapshot(job_id)
    return 0 if snapshot["papers"] and snapshot["analysis_ready_count"] == len(snapshot["papers"]) and not snapshot["issues"] else 2
