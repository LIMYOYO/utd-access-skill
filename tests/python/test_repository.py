import asyncio
from dataclasses import replace

import httpx
import pytest

from paper_access.budget import BudgetLedger
from paper_access.config import CredentialResolver
from paper_access.http import HttpClient
from paper_access.models import Artifact, AttemptOutcome, JobOptions
from paper_access.providers.base import AccessContext
from paper_access.providers.repository import Repository
from paper_access.store import JobStore


@pytest.mark.parametrize("case", ["valid", "wrong_id", "external_link", "login", "metadata_redirect", "content_redirect"])
def test_dspace_html_fallback_requires_matching_bitstream_and_same_origin(tmp_path, candidate, pdf_file, case):
    uid = "5349c200-b621-4b21-a4ca-45a65cb11112"
    origin = "https://repo.example"
    endpoint = f"/server/api/core/bitstreams/{uid}"
    paper = replace(candidate, uri=f"{origin}/bitstreams/{uid}/download")
    payload = pdf_file().path.read_bytes()
    calls = []
    def respond(request):
        calls.append(request.url.path)
        if request.url.path == f"/bitstreams/{uid}/download":
            return httpx.Response(200, headers={"content-type": "text/html"}, text=f'<title>DSpace</title><script>"dspaceVersion":"7.6","url":"{origin}/server/api"</script>' + ('<input type="password">' if case == "login" else ''))
        if request.url.path == endpoint:
            if case == "metadata_redirect":
                return httpx.Response(302, headers={"location": "https://elsewhere.example/metadata"})
            return httpx.Response(200, json={"uuid": uid if case != "wrong_id" else "different", "type": "bitstream", "_links": {"content": {"href": f"{origin if case != 'external_link' else 'https://elsewhere.example'}{endpoint}/content"}}})
        assert request.headers["host"] == "repo.example"
        assert request.url.path == endpoint + "/content"
        if case == "content_redirect":
            return httpx.Response(302, headers={"location": "https://elsewhere.example/file.pdf"})
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=payload)
    async def public(host):
        return ["93.184.216.34"]
    async def scenario():
        store = JobStore(tmp_path / "db"); options = JobOptions(tmp_path / "out"); job = store.create([], [], options)
        async with HttpClient(transport=httpx.MockTransport(respond), resolver=public) as http:
            ctx = AccessContext(http, BudgetLedger(store), CredentialResolver(), options, job)
            result = await Repository().acquire(paper, ctx, destination=tmp_path / "result.part")
            if case == "valid":
                assert isinstance(result, Artifact) and result.path.read_bytes() == payload
                assert result.source_uri == origin + endpoint + "/content"
            else:
                assert isinstance(result, AttemptOutcome)
                if case != "content_redirect":
                    assert endpoint + "/content" not in calls
    asyncio.run(scenario())


@pytest.mark.parametrize("case", ["valid", "login", "no_metadata"])
def test_oa_landing_uses_only_explicit_pdf_metadata(tmp_path, candidate, pdf_file, case):
    candidate = replace(candidate, uri="https://repo.example/article", format="landing")
    payload = pdf_file().path.read_bytes()
    calls=[]
    def respond(request):
        calls.append(request.url.path)
        if request.url.path == "/article":
            tag = '<meta name="citation_pdf_url" content="/full.pdf">' if case != "no_metadata" else '<a href="/full.pdf">Download</a>'
            return httpx.Response(200, headers={"content-type":"text/html"}, text=tag + ('<input type="password">' if case == "login" else ''))
        return httpx.Response(200, headers={"content-type":"application/pdf"}, content=payload)
    async def public(host):return ["93.184.216.34"]
    async def run():
        store=JobStore(tmp_path/"db");options=JobOptions(tmp_path/"out");job=store.create([],[],options)
        async with HttpClient(transport=httpx.MockTransport(respond),resolver=public) as http:
            result=await Repository().acquire(candidate,AccessContext(http,BudgetLedger(store),CredentialResolver(),options,job))
            if case=="valid":assert isinstance(result,Artifact) and result.path.read_bytes()==payload
            else:assert "/full.pdf" not in calls
    asyncio.run(run())
