"""Exact arXiv Atom lookup; preserves requested and returned version identity."""
import re
from dataclasses import replace
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from .base import metadata_response, ProviderFailure
from ..imports import normalize_identifier
from ..matching import match_identity
from ..models import Candidate, AttemptOutcome

ATOM = "{http://www.w3.org/2005/Atom}"


class Arxiv:
    name = "arxiv"

    def __init__(self):
        self._candidates = {}

    async def lookup(self, paper, context):
        if paper.identifier_kind != "arxiv":
            return paper
        response = await metadata_response("https://export.arxiv.org/api/query", self.name, context,
                                           params={"id_list": paper.identifier, "max_results": 1})
        try:
            entries = ElementTree.fromstring(response.content).findall(ATOM + "entry")
        except (ElementTree.ParseError, DefusedXmlException):
            raise ProviderFailure(AttemptOutcome("retryable_failure", self.name, "invalid_metadata")) from None
        if len(entries) != 1:
            raise ProviderFailure(AttemptOutcome("not_found", self.name, "no_exact_record"))
        entry = entries[0]
        identity = normalize_identifier(entry.findtext(ATOM + "id", ""))
        if not identity or identity[0] != "arxiv":
            raise ProviderFailure(AttemptOutcome("ambiguous_match", self.name, "metadata_identity_mismatch"))
        actual = identity[1]
        comparable = actual if re.search(r"v\d+$", paper.identifier) else re.sub(r"v\d+$", "", actual)
        if comparable.casefold() != paper.identifier.casefold():
            raise ProviderFailure(AttemptOutcome("ambiguous_match", self.name, "metadata_identity_mismatch"))
        title = " ".join(entry.findtext(ATOM + "title", "").split())
        authors = tuple(" ".join(author.findtext(ATOM + "name", "").split()) for author in entry.findall(ATOM + "author"))
        if not title or not authors or not all(authors):
            raise ProviderFailure(AttemptOutcome("retryable_failure", self.name, "invalid_metadata"))
        enriched = replace(paper, title=title, authors=authors)
        if paper.title and paper.authors and not match_identity(paper, [enriched]):
            raise ProviderFailure(AttemptOutcome("ambiguous_match", self.name, "metadata_identity_mismatch"))
        related = normalize_identifier(entry.findtext("{http://arxiv.org/schemas/atom}doi", ""))
        if related and related[0] in {"doi", "ssrn"}:
            from ..matching import link_versions
            link_versions("arxiv:" + actual, related[0] + ":" + related[1],
                          {"source": "https://export.arxiv.org/api/query?id_list=" + actual, "method": "arxiv_doi_field"}, context.budget.store)
        license_url = entry.findtext("{http://arxiv.org/schemas/atom}license")
        self._candidates[paper.paper_id] = Candidate(paper.paper_id, self.name, "arxiv:" + actual,
            "https://arxiv.org/pdf/" + actual, version="submittedVersion",
            version_evidence="arXiv Atom entry " + actual, license=license_url,
            provenance="https://arxiv.org/abs/" + actual)
        return enriched

    async def discover(self, paper, context):
        if paper.identifier_kind != "arxiv":
            return []
        if paper.paper_id not in self._candidates:
            await self.lookup(paper, context)
        return [self._candidates[paper.paper_id]]
