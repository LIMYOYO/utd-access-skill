import asyncio
from dataclasses import replace
from decimal import Decimal

import httpx
import pytest

from paper_access.budget import BudgetLedger
from paper_access.config import CredentialResolver
from paper_access.download import download_candidate
from paper_access.http import HttpClient
from paper_access.models import Artifact, AttemptOutcome, JobOptions
from paper_access.providers.base import AccessContext
from paper_access.store import JobStore


async def public(host):
    return ["93.184.216.34"]


def test_streamed_download_writes_part_and_keeps_response_out_of_memory(tmp_path, candidate, pdf_file):
    data = pdf_file().path.read_bytes()
    destination = tmp_path / "download.part"
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield data[:100]
            assert destination.exists() and destination.stat().st_size == 100
            yield data[100:]
    async def scenario():
        store = JobStore(tmp_path / "db")
        options = JobOptions(tmp_path / "out")
        job = store.create([], [], options)
        async with HttpClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, headers={"content-type": "application/pdf"}, stream=Stream())), resolver=public) as http:
            ctx = AccessContext(http, BudgetLedger(store), CredentialResolver(), options, job)
            result = await download_candidate(candidate, ctx, destination)
            assert isinstance(result, Artifact)
            assert result.path == destination and result.byte_count == len(data)
            assert destination.read_bytes() == data
    asyncio.run(scenario())


def test_response_size_limit_leaves_no_success_artifact(tmp_path, candidate):
    async def scenario():
        store = JobStore(tmp_path / "db"); options = JobOptions(tmp_path / "out")
        job = store.create([], [], options)
        async with HttpClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * 101)), resolver=public) as http:
            ctx = AccessContext(http, BudgetLedger(store), CredentialResolver(), options, job)
            result = await download_candidate(candidate, ctx, tmp_path / "oversized.part", max_bytes=100)
            assert isinstance(result, AttemptOutcome) and result.status != "verified_fulltext"
    asyncio.run(scenario())


def test_zero_budget_never_sends_paid_content_request(tmp_path, candidate, monkeypatch):
    monkeypatch.setenv("OPENALEX_API_KEY", "test-private")
    paid = replace(candidate, provider="openalex", location_id="W123", uri="https://content.openalex.org/works/W123.pdf", estimated_cost_usd=Decimal("0.01"))
    async def scenario():
        store = JobStore(tmp_path / "db"); options = JobOptions(tmp_path / "out")
        job = store.create([], [], options)
        def reject(request):
            raise AssertionError("zero budget must block before HTTP")
        async with HttpClient(transport=httpx.MockTransport(reject), resolver=public) as http:
            result = await download_candidate(paid, AccessContext(http, BudgetLedger(store), CredentialResolver(), options, job), tmp_path / "paid.part")
            assert result.status == "budget_exhausted"
    asyncio.run(scenario())


@pytest.mark.parametrize("estimate", ["0", "0.001"])
def test_metered_content_host_cannot_be_underpriced_by_candidate(tmp_path, candidate, monkeypatch, estimate):
    monkeypatch.setenv("OPENALEX_API_KEY", "test-private")
    metered = replace(candidate, provider="openalex", uri="https://content.openalex.org/works/W123.pdf", estimated_cost_usd=Decimal(estimate))
    async def scenario():
        store = JobStore(tmp_path / "db"); options = JobOptions(tmp_path / "out", max_cost_usd=Decimal("0.005")); job = store.create([], [], options)
        def reject(request):
            raise AssertionError("known metered route must reserve its actual upper bound")
        async with HttpClient(transport=httpx.MockTransport(reject), resolver=public) as http:
            result = await download_candidate(metered, AccessContext(http, BudgetLedger(store), CredentialResolver(), options, job), tmp_path / "paid.part")
            assert result.status == "budget_exhausted"
    asyncio.run(scenario())


def test_failed_paid_request_is_not_automatically_retried_or_refunded(tmp_path, candidate, monkeypatch):
    monkeypatch.setenv("OPENALEX_API_KEY", "test-private")
    calls = []
    paid = replace(candidate, provider="openalex", location_id="W123", uri="https://content.openalex.org/works/W123.pdf", estimated_cost_usd=Decimal("0.01"))
    def failure(request):
        calls.append(request)
        raise httpx.ReadError("interrupted")
    async def scenario():
        store = JobStore(tmp_path / "db"); options = JobOptions(tmp_path / "out", max_cost_usd=Decimal("0.01"))
        job = store.create([], [], options); budget = BudgetLedger(store)
        async with HttpClient(transport=httpx.MockTransport(failure), resolver=public) as http:
            result = await download_candidate(paid, AccessContext(http, budget, CredentialResolver(), options, job), tmp_path / "paid.part")
            assert result.status == "retryable_failure"
            assert budget.committed(job) == Decimal("0.01")
    asyncio.run(scenario())
    assert len(calls) == 1


def test_interrupted_stream_resumes_only_with_matching_strong_etag(tmp_path, candidate, pdf_file):
    payload = pdf_file().path.read_bytes()
    calls = []
    class Interrupted(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield payload[:100]
            raise httpx.ReadError("connection interrupted")
    def respond(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(200, headers={"content-type": "application/pdf", "accept-ranges": "bytes", "etag": '"v1"'}, stream=Interrupted())
        assert request.headers["range"] == "bytes=100-"
        assert request.headers["if-range"] == '"v1"'
        return httpx.Response(206, headers={"content-type": "application/pdf", "etag": '"v1"', "content-range": f"bytes 100-{len(payload)-1}/{len(payload)}"}, content=payload[100:])
    async def no_sleep(delay):
        pass
    async def scenario():
        store = JobStore(tmp_path / "db"); options = JobOptions(tmp_path / "out"); job = store.create([], [], options)
        async with HttpClient(transport=httpx.MockTransport(respond), resolver=public, sleep=no_sleep) as http:
            result = await download_candidate(candidate, AccessContext(http, BudgetLedger(store), CredentialResolver(), options, job), tmp_path / "resumed.part")
            assert isinstance(result, Artifact)
            assert result.path.read_bytes() == payload
    asyncio.run(scenario())
    assert len(calls) == 2


def test_server_ignoring_range_restarts_file_instead_of_appending(tmp_path, candidate):
    calls = []
    class Interrupted(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"old prefix"
            raise httpx.ReadError("interrupted")
    def respond(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(200, headers={"accept-ranges": "bytes", "etag": '"old"'}, stream=Interrupted())
        return httpx.Response(200, headers={"etag": '"new"'}, content=b"complete new object")
    async def no_sleep(delay):
        pass
    async def scenario():
        store = JobStore(tmp_path / "db"); options = JobOptions(tmp_path / "out"); job = store.create([], [], options)
        async with HttpClient(transport=httpx.MockTransport(respond), resolver=public, sleep=no_sleep) as http:
            result = await download_candidate(candidate, AccessContext(http, BudgetLedger(store), CredentialResolver(), options, job), tmp_path / "restarted.part")
            assert isinstance(result, Artifact) and result.path.read_bytes() == b"complete new object"
    asyncio.run(scenario())


def test_conflicting_range_total_requires_complete_restart(tmp_path, candidate):
    calls = []
    class Interrupted(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"a" * 100
            raise httpx.ReadError("interrupted")
    def respond(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(200, headers={"content-length": "1000", "accept-ranges": "bytes", "etag": '"same"'}, stream=Interrupted())
        if len(calls) == 2:
            return httpx.Response(206, headers={"etag": '"same"', "content-range": "bytes 100-199/200"}, content=b"b" * 100)
        assert "range" not in request.headers
        return httpx.Response(200, content=b"c" * 1000)
    async def no_sleep(delay):
        pass
    async def scenario():
        store = JobStore(tmp_path / "db"); options = JobOptions(tmp_path / "out"); job = store.create([], [], options)
        async with HttpClient(transport=httpx.MockTransport(respond), resolver=public, sleep=no_sleep) as http:
            result = await download_candidate(candidate, AccessContext(http, BudgetLedger(store), CredentialResolver(), options, job), tmp_path / "restarted.part")
            assert isinstance(result, Artifact) and result.path.read_bytes() == b"c" * 1000
    asyncio.run(scenario())
    assert len(calls) == 3
