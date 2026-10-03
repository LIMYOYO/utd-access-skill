"""Unpaywall DOI locations using the user's own contact address."""

from urllib.parse import quote

from .base import AccessContext, ProviderFailure, metadata, persistent_uri, verify_doi, object_list
from ..models import AttemptOutcome, Candidate, PaperInput


class Unpaywall:
    name = "unpaywall"

    async def discover(self, paper: PaperInput, context: AccessContext) -> list[Candidate]:
        if not paper.doi:
            return []
        email = context.credentials.get(self.name, "email")
        if not email:
            raise ProviderFailure(AttemptOutcome("needs_credentials", self.name, "missing_contact_email"))
        data = await metadata("https://api.unpaywall.org/v2/" + quote(paper.doi, safe="/"),
                              self.name, context, params={"email": email})
        verify_doi(data.get("doi", ""), paper, self.name)
        candidates = []
        for location in object_list(data.get("oa_locations"), self.name):
            if not location.get("url_for_pdf"):
                continue
            uri = persistent_uri(location["url_for_pdf"])
            location_id = persistent_uri(location.get("url_for_landing_page")) or uri
            if not location_id:
                continue
            candidates.append(Candidate(paper.paper_id, self.name, location_id, uri,
                                        version=location.get("version") or "unknown", version_evidence="Unpaywall oa_locations.version",
                                        license=location.get("license"), provenance=f"doi:{paper.doi}"))
        return candidates
