"""Fetch an explicitly discovered repository location through the shared client."""

from hashlib import sha256
from dataclasses import replace
from pathlib import Path
import re
from urllib.parse import urlsplit, urljoin
from uuid import uuid4

from bs4 import BeautifulSoup

from .base import AccessContext, ProviderFailure, metadata, object_field
from ..models import Artifact, AttemptOutcome, Candidate


class Repository:
    async def acquire(self, candidate: Candidate, context: AccessContext, *, destination: Path | None = None) -> Artifact | AttemptOutcome:
        from ..download import download_candidate
        identity = sha256((candidate.provider + candidate.location_id).encode()).hexdigest()[:16]
        destination = destination or context.options.output_dir / ".partial" / context.job_id / uuid4().hex / f"{candidate.paper_id}-{identity}.part"
        result = await download_candidate(candidate, context, destination, max_bytes=context.options.max_file_bytes)
        if not isinstance(result, Artifact) or result.mime_type != "text/html" or candidate.estimated_cost_usd != 0:
            return result
        if candidate.format == "landing" and result.byte_count <= 1024 * 1024:
            page = BeautifulSoup(result.path.read_bytes(), "html.parser")
            if page.select_one('input[type="password"]'):
                return AttemptOutcome("needs_login", candidate.provider, "repository_login_page")
            base = result.source_uri or candidate.uri or ""
            targets = {urljoin(base, tag.get("content", "")) for tag in page.select('meta[name="citation_pdf_url"]') if tag.get("content")}
            if len(targets) == 1:
                target = next(iter(targets))
                parsed, origin = urlsplit(target), urlsplit(base)
                if parsed.scheme in {"http", "https"} and parsed.netloc == origin.netloc and target != base:
                    return await download_candidate(replace(candidate, uri=target, format="pdf"), context, destination,
                                                    max_bytes=context.options.max_file_bytes)
        # DSpace's Angular download route can serve its app shell to HTTP
        # clients. Resolve that same bitstream via its documented REST link.
        # Never crawl arbitrary links or treat a login/challenge as a file.
        location = urlsplit(candidate.uri or "")
        match = re.fullmatch(r"/bitstreams/([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})/download", location.path)
        if not match or result.byte_count > 1024 * 1024:
            return result
        page = result.path.read_text(encoding="utf-8", errors="replace")
        origin = f"{location.scheme}://{location.netloc}"
        if "dspaceVersion" not in page or origin + "/server/api" not in page:
            return result
        if BeautifulSoup(page, "html.parser").select_one('input[type="password"]'):
            return AttemptOutcome("needs_login", candidate.provider, "repository_login_page")
        endpoint = origin + "/server/api/core/bitstreams/" + match[1]
        try:
            data = await metadata(endpoint, candidate.provider, context, follow_redirects=False)
            links = object_field(data.get("_links"), candidate.provider)
            content = object_field(links.get("content"), candidate.provider)
        except ProviderFailure as error:
            return error.outcome
        if data.get("uuid") != match[1] or data.get("type") != "bitstream" or content.get("href") != endpoint + "/content":
            return AttemptOutcome("ambiguous_match", candidate.provider, "repository_bitstream_mismatch")
        return await download_candidate(replace(candidate, uri=content["href"]), context, destination,
                                        max_bytes=context.options.max_file_bytes, follow_redirects=False)
