import asyncio
from dataclasses import replace
import httpx
import pytest
from paper_access.providers.arxiv import Arxiv
from paper_access.providers.base import AccessContext, ProviderFailure
from paper_access.http import HttpClient
from paper_access.budget import BudgetLedger
from paper_access.config import CredentialResolver
from paper_access.models import JobOptions
from paper_access.store import JobStore


def invoke(tmp_path, paper, xml):
    async def run():
        async def public(host): return ["93.184.216.34"]
        options = JobOptions(tmp_path / "out")
        store = JobStore(tmp_path / "db")
        job = store.create([paper], [], options)
        async with HttpClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=xml)), resolver=public) as http:
            context = AccessContext(http, BudgetLedger(store), CredentialResolver(), options, job)
            provider = Arxiv()
            enriched = await provider.lookup(paper, context)
            candidates = await provider.discover(enriched, context)
            return enriched, candidates
    return asyncio.run(run())


def atom(identifier="2401.01234v2"):
    return f'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/{identifier}</id><title>A study of service capacity</title><author><name>Jane Smith</name></author><published>2024-01-02T00:00:00Z</published></entry></feed>'''


def test_arxiv_exact_version_and_metadata(tmp_path, expected_paper):
    paper = replace(expected_paper, identifier_kind="arxiv", identifier="2401.01234v2", title="", authors=())
    enriched, candidates = invoke(tmp_path, paper, atom())
    assert enriched.title == "A study of service capacity"
    assert enriched.authors == ("Jane Smith",)
    assert enriched.paper_id == paper.paper_id
    assert candidates[0].uri == "https://arxiv.org/pdf/2401.01234v2"
    assert candidates[0].version == "submittedVersion"


def test_arxiv_wrong_version_metadata_rejected(tmp_path, expected_paper):
    paper = replace(expected_paper, identifier_kind="arxiv", identifier="2401.01234v1")
    with pytest.raises(ProviderFailure) as error:
        invoke(tmp_path, paper, atom())
    assert error.value.outcome.reason_code == "metadata_identity_mismatch"


def test_arxiv_unversioned_input_pins_returned_version(tmp_path, expected_paper):
    paper = replace(expected_paper, identifier_kind="arxiv", identifier="2401.01234", title="", authors=())
    enriched, candidates = invoke(tmp_path, paper, atom())
    assert enriched.identifier == "2401.01234"
    assert candidates[0].uri.endswith("v2")


def test_source_gate_serializes_process_connections_and_spaces_calls(tmp_path):
    from paper_access.source_gate import SourceGate
    from paper_access.http import RateLimited
    async def scenario():
        clock = [100.0]
        delays = []
        async def sleep(delay):
            delays.append(delay)
            clock[0] += delay
        first = SourceGate(tmp_path / "rate.sqlite", now=lambda: clock[0], sleep=sleep)
        second = SourceGate(tmp_path / "rate.sqlite", now=lambda: clock[0], sleep=sleep)
        async with first.slot("arxiv", 3):
            with pytest.raises(RateLimited):
                async with second.slot("arxiv", 3):
                    pass
        async with second.slot("arxiv", 3):
            pass
        assert delays == [3]
    asyncio.run(scenario())


def test_arxiv_retry_after_survives_new_http_client(tmp_path):
    from paper_access.source_gate import SourceGate
    from paper_access.http import RateLimited
    async def scenario():
        clock = [100.0]
        calls = []
        async def sleep(delay): clock[0] += delay
        async def public(host): return ["93.184.216.34"]
        def respond(request):
            calls.append(request)
            return httpx.Response(429, headers={"retry-after": "3600"}) if len(calls) == 1 else httpx.Response(200)
        for index in range(2):
            async with HttpClient(transport=httpx.MockTransport(respond), resolver=public, sleep=sleep, monotonic=lambda: clock[0]) as http:
                http._source_gate = SourceGate(tmp_path / "rate.sqlite", now=lambda: clock[0], sleep=sleep)
                if index == 0:
                    assert (await http.request("GET", "https://export.arxiv.org/api/query", provider="arxiv", max_attempts=1)).status_code == 429
                    clock[0] += 3
                else:
                    with pytest.raises(RateLimited):
                        await http.request("GET", "https://export.arxiv.org/api/query", provider="arxiv", max_attempts=1)
        assert len(calls) == 1
    asyncio.run(scenario())
