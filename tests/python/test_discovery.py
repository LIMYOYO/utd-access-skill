import asyncio
from decimal import Decimal

import httpx
import pytest

from paper_access.budget import BudgetLedger
from paper_access.config import CredentialResolver
from paper_access.http import HttpClient
from paper_access.models import JobOptions, PaperInput, SourceRef
from paper_access.providers.base import AccessContext, ProviderFailure
from paper_access.providers.crossref import Crossref
from paper_access.providers.openalex import OpenAlex
from paper_access.providers.unpaywall import Unpaywall
from paper_access.store import JobStore


PAPER = PaperInput("doi", "10.1234/one", (SourceRef("input.txt", 1, "10.1234/one"),))


async def public(host):
    return ["93.184.216.34"]


def invoke(tmp_path, provider, data, *, credentials=None, code=200, lookup=False):
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(code, json=data)
    async def scenario():
        store = JobStore(tmp_path / "jobs.sqlite")
        options = JobOptions(tmp_path / "out")
        job = store.create([PAPER], [], options)
        async with HttpClient(transport=httpx.MockTransport(respond), resolver=public) as http:
            ctx = AccessContext(http, BudgetLedger(store), credentials or CredentialResolver(), options, job)
            return await (provider.lookup(PAPER, ctx) if lookup else provider.discover(PAPER, ctx))
    return asyncio.run(scenario()), requests


def test_crossref_enriches_identity_and_does_not_treat_tdm_link_as_download(tmp_path):
    data = {"status": "ok", "message": {"DOI": "10.1234/one", "title": ["A paper"],
            "author": [{"given": "Jane", "family": "Smith"}], "published": {"date-parts": [[2023, 1]]},
            "link": [{"URL": "https://publisher.example/tdm", "intended-application": "similarity-checking"}]}}
    paper, requests = invoke(tmp_path, Crossref(), data, lookup=True)
    assert paper.title == "A paper" and paper.authors == ("Jane Smith",) and paper.year == 2023
    candidates, _ = invoke(tmp_path, Crossref(), data)
    assert candidates == []
    assert requests[0].url.path == "/works/10.1234/one"


def test_openalex_preserves_version_license_and_stable_provenance(tmp_path):
    data = {"id": "https://openalex.org/W123", "doi": "https://doi.org/10.1234/one", "title": "A paper",
            "locations": [{"id": "pmh:oai:repo:123", "is_oa": True, "pdf_url": "https://repo.example/123.pdf",
                           "landing_page_url": "https://repo.example/123", "version": "acceptedVersion", "license": "cc-by", "source": None},
                          {"id": "doi:10.1234/one", "is_oa": False, "pdf_url": "https://publisher.example/paid.pdf", "version": "publishedVersion"}],
            "content_urls": {"pdf": "https://content.openalex.org/works/W123.pdf"}}
    candidates, requests = invoke(tmp_path, OpenAlex(), data)
    assert len(candidates) == 2
    repo = candidates[0]
    assert repo.version == "acceptedVersion" and repo.license == "cc-by"
    assert repo.location_id == "pmh:oai:repo:123"
    assert repo.uri == "https://repo.example/123.pdf"
    assert candidates[1].estimated_cost_usd == Decimal("0.01")
    assert candidates[1].version == "unknown"
    assert len(requests) == 1  # Discovery never requests billable content.


def test_unpaywall_missing_email_does_not_make_request(tmp_path, monkeypatch):
    monkeypatch.delenv("UNPAYWALL_EMAIL", raising=False)
    with pytest.raises(ProviderFailure) as error:
        invoke(tmp_path, Unpaywall(), {})
    assert error.value.outcome.status == "needs_credentials"


def test_unpaywall_oa_locations_and_email_query(tmp_path, monkeypatch):
    monkeypatch.setenv("UNPAYWALL_EMAIL", "researcher@university.example")
    data = {"doi": "10.1234/one", "oa_locations": [{"url_for_pdf": "https://repo.example/file.pdf",
            "url_for_landing_page": "https://repo.example/paper", "version": "submittedVersion", "license": None,
            "host_type": "repository", "evidence": "oa repository"}]}
    candidates, requests = invoke(tmp_path, Unpaywall(), data)
    assert len(candidates) == 1 and candidates[0].version == "submittedVersion"
    assert candidates[0].license is None
    assert requests[0].url.params["email"] == "researcher@university.example"


def test_wrong_doi_metadata_cannot_generate_candidates(tmp_path):
    with pytest.raises(ProviderFailure) as error:
        invoke(tmp_path, OpenAlex(), {"doi": "https://doi.org/10.1234/other", "locations": []})
    assert error.value.outcome.status == "ambiguous_match"


def test_404_has_distinct_not_found_reason(tmp_path):
    with pytest.raises(ProviderFailure) as error:
        invoke(tmp_path, OpenAlex(), {}, code=404)
    assert error.value.outcome.status == "not_found"


def test_signed_links_are_not_persistable_candidates(tmp_path):
    data = {"doi": "https://doi.org/10.1234/one", "locations": [{"id": "pmh:one", "is_oa": True,
            "pdf_url": "https://repo.example/paper?X-Amz-Signature=secret", "version": "acceptedVersion"}]}
    candidates, _ = invoke(tmp_path, OpenAlex(), data)
    assert candidates[0].location_id == "pmh:one"
    assert candidates[0].uri is None
    assert "secret" not in repr(candidates)


def test_azure_sas_link_is_not_retained_in_candidate(tmp_path):
    data = {"doi": "https://doi.org/10.1234/one", "locations": [{"id": "pmh:one", "is_oa": True,
            "pdf_url": "https://repo.example/paper?sv=2022-11-02&se=2026-09-27&sp=r&sig=secret", "version": "acceptedVersion"}]}
    candidates, _ = invoke(tmp_path, OpenAlex(), data)
    assert candidates[0].uri is None
    assert "secret" not in repr(candidates)


@pytest.mark.parametrize(("provider", "data", "lookup"), [
    (OpenAlex(), {"doi": "10.1234/one", "locations": [None]}, False),
    (OpenAlex(), {"doi": "10.1234/one", "locations": "wrong"}, False),
    (Crossref(), {"message": None}, True),
    (Unpaywall(), {"doi": "10.1234/one", "oa_locations": [None]}, False),
])
def test_malformed_nested_metadata_is_a_provider_failure(tmp_path, monkeypatch, provider, data, lookup):
    monkeypatch.setenv("UNPAYWALL_EMAIL", "researcher@university.example")
    with pytest.raises(ProviderFailure) as error:
        invoke(tmp_path, provider, data, lookup=lookup)
    assert error.value.outcome.reason_code == "invalid_metadata"


def test_title_lookup_requires_unique_full_bibliographic_match(tmp_path):
    from dataclasses import replace
    query = replace(PAPER, identifier_kind="title", identifier="A study of service systems", title="A study of service systems", authors=("Jane Smith",), year=2024)
    row = {"DOI": "10.1234/correct", "title": [query.title], "author": [{"given": "Jane", "family": "Smith"}], "published": {"date-parts": [[2024]]}}
    async def run(rows):
        store = JobStore(tmp_path / "title-db")
        options = JobOptions(tmp_path / "out")
        job = store.create([query], [], options)
        async with HttpClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"message": {"items": rows}})), resolver=public) as http:
            return await Crossref().resolve_title(query, AccessContext(http, BudgetLedger(store), CredentialResolver(), options, job))
    result = asyncio.run(run([dict(row, author=[{"given": "Other", "family": "Author"}]), row]))
    assert result.doi == "10.1234/correct" and result.paper_id == query.paper_id
    with pytest.raises(ProviderFailure):
        asyncio.run(run([row, dict(row, DOI="10.1234/another")]))


def test_openalex_retains_oa_landing_page_when_pdf_url_missing(tmp_path):
    data = {"doi": "10.1234/one", "locations": [{"id": "repo:landing", "is_oa": True,
            "landing_page_url": "https://repo.example/article", "pdf_url": None, "version": "acceptedVersion"}]}
    candidates, _ = invoke(tmp_path, OpenAlex(), data)
    assert candidates[0].uri == "https://repo.example/article"
    assert candidates[0].format == "landing"
