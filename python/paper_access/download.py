"""Download one candidate to a temporary file; never claims verification."""

from hashlib import file_digest
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4
import time

from .http import NetworkFailure, RateLimited, _retry_after
from .models import Artifact, AttemptOutcome, Candidate
from .providers.base import AccessContext, persistent_uri


async def download_candidate(candidate: Candidate, context: AccessContext, destination: Path,
                             *, max_bytes: int = 100 * 1024 * 1024, follow_redirects: bool = True) -> Artifact | AttemptOutcome:
    if not candidate.uri:
        return AttemptOutcome("retryable_failure", candidate.provider, "refresh_location_required")
    params = None
    metered_host = urlsplit(candidate.uri).hostname == "content.openalex.org"
    paid = candidate.estimated_cost_usd > 0 or metered_host
    if paid:
        if candidate.provider != "openalex" or urlsplit(candidate.uri).hostname != "content.openalex.org":
            return AttemptOutcome("needs_rights_review", candidate.provider, "unknown_pricing_route")
        key = context.credentials.get("openalex", "api_key")
        if not key:
            return AttemptOutcome("needs_credentials", candidate.provider, "missing_api_key")
        cost_bound = max(candidate.estimated_cost_usd, Decimal("0.01"))
        if not context.budget.reserve(context.job_id, uuid4().hex, cost_bound):
            return AttemptOutcome("budget_exhausted", candidate.provider, "cost_limit_reached")
        params = {"api_key": key}
    try:
        response = await context.http.request("GET", candidate.uri, provider=candidate.provider,
                                              params=params, fulltext=True, max_bytes=max_bytes,
                                              destination=destination, max_attempts=1 if paid else 3,
                                              follow_redirects=follow_redirects)
    except RateLimited as error:
        return AttemptOutcome("rate_limited", candidate.provider, "source_cooldown", next_retry_at=error.next_retry_at)
    except NetworkFailure:
        return AttemptOutcome("retryable_failure", candidate.provider, "download_failed")
    if response.status_code not in {200, 206}:
        status = {401: "needs_credentials", 403: "needs_login", 404: "not_found", 429: "rate_limited"}.get(response.status_code, "retryable_failure")
        next_retry = time.time() + max(1, _retry_after(response.headers.get("retry-after"))) if response.status_code == 429 else None
        return AttemptOutcome(status, candidate.provider, f"http_{response.status_code}", next_retry_at=next_retry)
    with destination.open("rb") as stream:
        digest = file_digest(stream, "sha256").hexdigest()
    return Artifact(destination, digest, response.headers.get("content-type", "application/octet-stream").split(";", 1)[0],
                    destination.stat().st_size, version=candidate.version, provider=candidate.provider,
                    source_uri=persistent_uri(str(response.request.url)))
