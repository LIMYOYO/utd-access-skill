"""Free single-work discovery; cached content stays a separately budgeted route."""

from decimal import Decimal
from urllib.parse import quote

from .base import AccessContext, metadata, persistent_uri, verify_doi, object_field, object_list
from ..models import Candidate, PaperInput


class OpenAlex:
    name = "openalex"

    async def discover(self, paper: PaperInput, context: AccessContext) -> list[Candidate]:
        if not paper.doi:
            return []
        key = context.credentials.get(self.name, "api_key")
        data = await metadata("https://api.openalex.org/works/https://doi.org/" + quote(paper.doi, safe="/"),
                              self.name, context, params={"api_key": key} if key else None)
        verify_doi(data.get("doi", ""), paper, self.name)
        candidates = []
        for location in object_list(data.get("locations"), self.name):
            if location.get("is_oa") is not True:
                continue
            raw_uri = location.get("pdf_url") or location.get("landing_page_url")
            if not raw_uri:
                continue
            uri = persistent_uri(raw_uri)
            location_id = location.get("id") or persistent_uri(location.get("landing_page_url")) or uri
            if not location_id:
                continue
            candidates.append(Candidate(paper.paper_id, self.name, location_id, uri,
                                        version=location.get("version") or "unknown", version_evidence="OpenAlex location.version",
                                        license=location.get("license"), provenance=data.get("id", ""),
                                        format="pdf" if location.get("pdf_url") else "landing"))
        content = object_field(data.get("content_urls") or {}, self.name)
        work_id = (data.get("id") or "").rsplit("/", 1)[-1]
        if content.get("pdf") and work_id.startswith("W") and work_id[1:].isdigit():
            candidates.append(Candidate(paper.paper_id, self.name, work_id,
                                        f"https://content.openalex.org/works/{work_id}.pdf",
                                        provenance=data.get("id", ""), estimated_cost_usd=Decimal("0.01")))
        return candidates
