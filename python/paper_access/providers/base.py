"""Shared provider contract and safe metadata helpers."""

from dataclasses import dataclass
from typing import Protocol
import time
from urllib.parse import parse_qsl, urlsplit

from ..budget import BudgetLedger
from ..config import CredentialResolver
from ..http import HttpClient, NetworkFailure, RateLimited, _retry_after
from ..imports import normalize_identifier
from ..models import Artifact, AttemptOutcome, Candidate, JobOptions, PaperInput


@dataclass(frozen=True)
class AccessContext:
    http: HttpClient
    budget: BudgetLedger
    credentials: CredentialResolver
    options: JobOptions
    job_id: str


class Provider(Protocol):
    async def discover(self, paper: PaperInput, context: AccessContext) -> list[Candidate]: ...
    async def acquire(self, candidate: Candidate, context: AccessContext) -> Artifact | AttemptOutcome: ...


class ProviderFailure(RuntimeError):
    def __init__(self, outcome: AttemptOutcome):
        self.outcome = outcome
        super().__init__(f"{outcome.provider}: {outcome.reason_code}")


def object_field(value, provider: str) -> dict:
    if not isinstance(value, dict):
        raise ProviderFailure(AttemptOutcome("retryable_failure", provider, "invalid_metadata"))
    return value


def object_list(value, provider: str) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ProviderFailure(AttemptOutcome("retryable_failure", provider, "invalid_metadata"))
    return value


async def metadata_response(url: str, provider: str, context: AccessContext, *, params=None, follow_redirects: bool = True):
    try:
        response = await context.http.request("GET", url, provider=provider, params=params, follow_redirects=follow_redirects)
    except RateLimited as error:
        raise ProviderFailure(AttemptOutcome("rate_limited", provider, "source_cooldown", next_retry_at=error.next_retry_at)) from None
    except NetworkFailure:
        raise ProviderFailure(AttemptOutcome("retryable_failure", provider, "network_failure")) from None
    code = response.status_code
    if code != 200:
        status = {401: "needs_credentials", 403: "needs_login", 404: "not_found", 429: "rate_limited"}.get(code, "retryable_failure")
        next_retry = time.time() + max(1, _retry_after(response.headers.get("retry-after"))) if code == 429 else None
        raise ProviderFailure(AttemptOutcome(status, provider, f"http_{code}", next_retry_at=next_retry))
    return response


async def metadata(url: str, provider: str, context: AccessContext, *, params=None, follow_redirects: bool = True) -> dict:
    response = await metadata_response(url, provider, context, params=params, follow_redirects=follow_redirects)
    try:
        data = response.json()
    except ValueError:
        raise ProviderFailure(AttemptOutcome("retryable_failure", provider, "invalid_json")) from None
    if not isinstance(data, dict):
        raise ProviderFailure(AttemptOutcome("retryable_failure", provider, "invalid_metadata"))
    return data


def verify_doi(value: str, paper: PaperInput, provider: str) -> None:
    if not isinstance(value, str) or normalize_identifier(value) != normalize_identifier(paper.doi or ""):
        raise ProviderFailure(AttemptOutcome("ambiguous_match", provider, "metadata_identity_mismatch"))


def persistent_uri(url: str | None) -> str | None:
    if not url or not isinstance(url, str):
        return None
    try:
        parsed = urlsplit(url)
        sensitive = ("token", "signature", "credential", "api_key", "apikey", "expires", "authorization")
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            return None
        if any(key.lower() in {"sig", "sas", "key", "auth", "access_key"} or any(part in key.lower() for part in sensitive)
               for key, _ in parse_qsl(parsed.query)):
            return None
    except ValueError:
        return None
    return url
