"""Shared records; input provenance survives deduplication."""

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class SourceRef:
    path: str
    line: int
    raw: str


@dataclass(frozen=True)
class ImportIssue:
    path: str
    line: int
    raw: str
    reason: str


@dataclass(frozen=True)
class PaperInput:
    identifier_kind: str
    identifier: str
    sources: tuple[SourceRef, ...]
    title: str = ""
    authors: tuple[str, ...] = ()
    year: int | None = None
    resolved_doi: str | None = None

    @property
    def paper_id(self) -> str:
        identity = f"{self.identifier_kind}:{self.identifier}"
        if self.identifier_kind == "title":
            # Unresolved titles must not merge distinct papers or input records.
            identity += repr((self.authors, self.year, self.sources))
        return sha256(identity.encode()).hexdigest()[:24]

    @property
    def doi(self) -> str | None:
        if self.identifier_kind == "doi":
            return self.identifier
        if self.identifier_kind == "nber":
            return f"10.3386/{self.identifier}"
        if self.identifier_kind == "ssrn":
            return f"10.2139/ssrn.{self.identifier}"
        return self.resolved_doi


@dataclass(frozen=True)
class JobOptions:
    output_dir: Path
    version_policy: str = "best-available"
    purpose: str = "reading"
    max_cost_usd: Decimal = Decimal("0")
    max_file_bytes: int = 100 * 1024 * 1024
    institution: dict | None = None
    validation_policy: str = "advisory"

    def __post_init__(self) -> None:
        if self.validation_policy not in {"advisory", "strict"}:
            raise ValueError("invalid validation policy")
        if self.version_policy not in {"best-available", "published-only"}:
            raise ValueError("invalid version policy")
        if self.purpose not in {"reading", "tdm", "ai"}:
            raise ValueError("invalid purpose")
        if not self.max_cost_usd.is_finite() or self.max_cost_usd < 0:
            raise ValueError("budget must be finite and nonnegative")
        if not isinstance(self.max_file_bytes, int) or self.max_file_bytes <= 0:
            raise ValueError("file size limit must be a positive integer")
        from .institution import validate_profile
        object.__setattr__(self, "institution", validate_profile(self.institution) or None)
        object.__setattr__(self, "output_dir", self.output_dir.expanduser().resolve())


STATUSES = frozenset({"resolved", "queued", "downloaded_fulltext", "downloaded_unverified", "verified_fulltext",
                      "needs_login", "needs_credentials", "needs_rights_review", "ambiguous_match",
                      "retryable_failure", "not_found", "budget_exhausted", "rate_limited", "invalid_input"})


@dataclass(frozen=True)
class AttemptOutcome:
    status: str
    provider: str
    reason_code: str
    next_retry_at: float | None = None
    redacted_detail: str = ""
    cost_usd: Decimal | None = None

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError("invalid attempt status")
        if self.cost_usd is not None and (not self.cost_usd.is_finite() or self.cost_usd < 0):
            raise ValueError("invalid attempt cost")


@dataclass(frozen=True)
class Artifact:
    path: Path
    sha256: str
    mime_type: str
    byte_count: int
    pages: int | None = None
    version: str = "unknown"
    provider: str = ""
    source_uri: str | None = None


@dataclass(frozen=True)
class Candidate:
    paper_id: str
    provider: str
    location_id: str
    uri: str | None
    version: str = "unknown"
    version_evidence: str = ""
    format: str = "pdf"
    license: str | None = None
    provenance: str = ""
    estimated_cost_usd: Decimal = Decimal("0")
    usage: tuple[str, ...] = ("reading",)


@dataclass(frozen=True)
class ValidationResult:
    status: str
    reason_code: str
    identity_evidence: str = ""
    pages: int | None = None
    mime_type: str = ""
    extraction_quality: str = "unknown"
