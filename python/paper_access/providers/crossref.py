"""Crossref supplies identity metadata, not a blanket download entitlement."""

from dataclasses import replace
from urllib.parse import quote

from .base import AccessContext, metadata, verify_doi, object_field, object_list, ProviderFailure
from ..models import AttemptOutcome
from ..models import Candidate, PaperInput


class Crossref:
    name = "crossref"

    async def lookup(self, paper: PaperInput, context: AccessContext) -> PaperInput:
        if not paper.doi:
            return paper
        result = await metadata("https://api.crossref.org/works/" + quote(paper.doi, safe=""), self.name, context)
        data = object_field(result.get("message", {}), self.name)
        verify_doi(data.get("DOI", ""), paper, self.name)
        author_rows = object_list(data.get("author"), self.name)
        if any(any(a.get(key) is not None and not isinstance(a[key], str) for key in ("given", "family", "name")) for a in author_rows):
            raise ProviderFailure(AttemptOutcome("retryable_failure", self.name, "invalid_metadata"))
        authors = tuple(" ".join(filter(None, (a.get("given"), a.get("family")))) or a.get("name", "") for a in author_rows)
        parts = object_field(data.get("published", {}), self.name).get("date-parts", [])
        if not isinstance(parts, list) or any(not isinstance(row, list) or any(not isinstance(n, int) for n in row) for row in parts):
            raise ProviderFailure(AttemptOutcome("retryable_failure", self.name, "invalid_metadata"))
        year = parts[0][0] if parts and parts[0] else paper.year
        titles = data.get("title") or []
        if not isinstance(titles, list) or any(not isinstance(title, str) for title in titles):
            raise ProviderFailure(AttemptOutcome("retryable_failure", self.name, "invalid_metadata"))
        return replace(paper, title=paper.title or (titles[0] if titles else ""),
                       authors=paper.authors or authors, year=paper.year or year)

    async def resolve_title(self, paper: PaperInput, context: AccessContext) -> PaperInput:
        from ..matching import match_identity
        from ..imports import normalize_identifier
        if not paper.authors:
            raise ProviderFailure(AttemptOutcome("ambiguous_match", self.name, "title_requires_authors_or_identifier"))
        data = await metadata("https://api.crossref.org/works", self.name, context,
                              params={"query.bibliographic": paper.title, "rows": 5})
        rows = object_list(object_field(data.get("message", {}), self.name).get("items"), self.name)
        records = []
        for row in rows:
            doi = normalize_identifier(row.get("DOI", "")) if isinstance(row.get("DOI"), str) else None
            titles = row.get("title")
            authors = object_list(row.get("author"), self.name)
            if not doi or not isinstance(titles, list) or not titles or not isinstance(titles[0], str):
                continue
            if any(any(a.get(key) is not None and not isinstance(a[key], str) for key in ("given", "family", "name")) for a in authors):
                continue
            names = tuple(" ".join(filter(None, (a.get("given"), a.get("family")))) or a.get("name", "") for a in authors)
            parts = object_field(row.get("published", {}), self.name).get("date-parts", [])
            year = parts[0][0] if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0] and isinstance(parts[0][0], int) else None
            records.append(PaperInput(*doi, paper.sources, titles[0], names, year))
        matches = match_identity(paper, records)
        unique = {record.doi: record for record in matches if record.doi}
        if len(unique) != 1:
            raise ProviderFailure(AttemptOutcome("ambiguous_match", self.name, "title_match_requires_confirmation"))
        return replace(paper, resolved_doi=next(iter(unique)))

    async def discover(self, paper: PaperInput, context: AccessContext) -> list[Candidate]:
        return []
