import asyncio
import httpx
import pytest
from paper_access.models import PaperInput, SourceRef, JobOptions, Candidate
from paper_access.store import JobStore
from paper_access.runner import run_job
from paper_access.http import HttpClient
from paper_access.budget import BudgetLedger
from paper_access.config import CredentialResolver
from paper_access.providers.base import AccessContext


def test_ten_thousand_records_persist_and_resume_after_interruption(tmp_path):
    papers=[PaperInput("doi",f"10.1234/scale{i}",(SourceRef("fixture.csv",i+1,str(i)),),title=f"Service systems study number {i}",authors=("Jane Smith",)) for i in range(10000)]
    store=JobStore(tmp_path/"db");options=JobOptions(tmp_path/"out");job=store.create(papers,[],options)
    class Provider:
        def __init__(self, crash=False): self.calls=[];self.crash=crash
        async def discover(self,paper,context):
            self.calls.append(paper.paper_id)
            if self.crash and len(self.calls)==500:raise RuntimeError("injected interruption")
            if int(paper.identifier.removeprefix("10.1234/scale"))%1000:return []
            return [Candidate(paper.paper_id,"fixture",paper.identifier,"https://fixture.example/"+paper.identifier,version="acceptedVersion")]
    async def run(provider):
        async def public(host):return ["93.184.216.34"]
        def respond(request):
            doi=request.url.path.lstrip("/")
            content='<article><front><article-meta><article-id pub-id-type="doi">'+doi+'</article-id></article-meta></front><body><p>'+('Service systems analysis. '*50)+'</p></body></article>'
            return httpx.Response(200,headers={"content-type":"application/xml"},content=content.encode())
        async with HttpClient(transport=httpx.MockTransport(respond),resolver=public) as http:
            return await run_job(job,store,AccessContext(http,BudgetLedger(store),CredentialResolver(),options,job),providers=[provider])
    with pytest.raises(RuntimeError,match="injected"):
        asyncio.run(run(Provider(crash=True)))
    first=store.snapshot(job)
    verified_ids={p["paper_id"] for p in first["papers"] if p["status"]=="verified_fulltext"}
    assert verified_ids
    resumed=Provider()
    assert asyncio.run(run(resumed))==2
    final=store.snapshot(job)
    assert len(final["papers"])==10000 and final["verified_count"]==10
    assert not verified_ids.intersection(resumed.calls)
    assert len(final["artifacts"])==10
    assert len((tmp_path/"out"/"manifest.jsonl").read_text().splitlines())==10000
