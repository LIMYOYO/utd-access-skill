"""Browser access routes and validated manual file completion."""
import hashlib
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl, quote
from .models import Artifact, Candidate, AttemptOutcome
from .providers.base import persistent_uri


def validate_profile(profile: dict | None) -> dict:
    profile = dict(profile or {})
    allowed = {"institution_name", "resolver_base_url", "libkey_library_id", "openathens_domain"}
    if set(profile) - allowed or any(not isinstance(value, str) for value in profile.values()):
        raise ValueError("invalid institution profile fields")
    resolver = profile.get("resolver_base_url")
    if resolver and (not persistent_uri(resolver) or urlsplit(resolver).scheme != "https"):
        raise ValueError("institution resolver must be a stable HTTPS URL")
    library = profile.get("libkey_library_id")
    if library and not library.isdigit():
        raise ValueError("LibKey library ID must contain digits only")
    domain = profile.get("openathens_domain")
    if domain:
        import re
        if not re.fullmatch(r"[a-zA-Z0-9]+(?:[.-][a-zA-Z0-9]+)*\.[a-zA-Z]{2,}", domain):
            raise ValueError("invalid OpenAthens domain")
    return profile


def build_access_links(paper, institution: dict | None) -> list[dict[str, str]]:
    profile = validate_profile(institution)
    links = []
    if paper.doi:
        doi_path = quote(paper.doi, safe="/")
        links.append({"label": "DOI", "url": "https://doi.org/" + doi_path})
        library = profile.get("libkey_library_id")
        links.append({"label": "LibKey", "url": "https://libkey.io/" + ("libraries/" + library + "/" if library else "") + doi_path})
        if profile.get("openathens_domain"):
            links.append({"label": profile.get("institution_name") or "Institution login",
                          "url": "https://go.openathens.net/redirector/" + profile["openathens_domain"] + "?" + urlencode({"url": "https://doi.org/" + doi_path})})
    elif paper.identifier_kind == "arxiv":
        links.append({"label": "arXiv", "url": "https://arxiv.org/abs/" + quote(paper.identifier, safe="/")})
    elif paper.identifier_kind == "repec":
        links.append({"label": "RePEc record", "url": "https://ideas.repec.org/cgi-bin/htsearch?" + urlencode({"q": paper.identifier})})
    if profile.get("resolver_base_url"):
        parsed = urlsplit(profile["resolver_base_url"])
        params = dict(parse_qsl(parsed.query))
        params.update({"url_ver": "Z39.88-2004", "rfr_id": "info:sid/utd-access-skill", "rft.atitle": paper.title})
        if paper.doi:
            params["rft_id"] = "info:doi/" + paper.doi
        links.append({"label": profile.get("institution_name") or "Library resolver",
                      "url": urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(params), ""))})
    return links


def import_file(job_id: str, paper_id: str, path: Path, store, *, version: str = "unknown", version_evidence: str = "user-specified on local import") -> int:
    from .runner import _paper
    from .validate import assess_artifact, analysis_allowed, USABLE_STATUSES
    from .extract import extract_text
    from .report import write_report
    if version not in {"unknown", "publishedVersion", "acceptedVersion", "submittedVersion"}:
        raise ValueError("invalid document version")
    path = Path(path).expanduser().resolve()
    options = store.options(job_id)
    if not path.is_file() or path.stat().st_size > options.max_file_bytes:
        raise ValueError("source file is missing or exceeds the job size limit")
    owner = store.acquire_lease(job_id)
    temporary = None
    staged = False
    try:
        snapshot = store.snapshot(job_id)
        saved = next((paper for paper in snapshot["papers"] if paper["paper_id"] == paper_id), None)
        if saved is None:
            raise ValueError("unknown paper ID for this job")
        def fail(status, reason):
            store.record_attempt(job_id, paper_id, AttemptOutcome(status, "manual", reason), owner=owner,
                                 preserve_status=saved["status"] == "verified_fulltext")
            return 2
        if options.purpose != "reading":
            return fail("needs_rights_review", "manual_import_requires_reading_purpose")
        if options.version_policy == "published-only" and version != "publishedVersion":
            return fail("not_found", "version_policy_mismatch")
        temporary = options.output_dir / ".partial" / job_id / owner / "manual.part"
        temporary.parent.mkdir(parents=True, exist_ok=True)
        with path.open("rb") as source, temporary.open("wb") as target:
            remaining = options.max_file_bytes + 1
            while remaining:
                block = source.read(min(65536, remaining))
                if not block:
                    break
                target.write(block)
                remaining -= len(block)
            if not remaining:
                raise ValueError("source grew beyond the job size limit")
        with temporary.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        mime = {".pdf": "application/pdf", ".xml": "application/xml", ".html": "text/html"}.get(path.suffix.lower(), "application/octet-stream")
        artifact = Artifact(temporary, digest, mime, temporary.stat().st_size, version=version, provider="manual")
        candidate = Candidate(paper_id, "manual", "sha256:" + digest, None, version=version,
                              version_evidence=version_evidence)
        validation = assess_artifact(artifact, _paper(saved), candidate)
        if validation.status not in USABLE_STATUSES:
            return fail(validation.status, validation.reason_code)
        if saved['status']=='verified_fulltext' and validation.status!='verified_fulltext':
            return fail(validation.status, validation.reason_code)
        suffix = {"application/pdf": ".pdf", "application/xml": ".xml", "text/html": ".html"}[validation.mime_type]
        final = options.output_dir / "files" / f"{paper_id}-{digest[:16]}{suffix}"
        completed = replace(artifact, path=final, pages=validation.pages, mime_type=validation.mime_type)
        store.renew_lease(job_id, owner)
        store.stage_artifact(job_id, paper_id, completed, candidate, validation, owner, temporary=temporary)
        staged = True
        store.publish_artifact(job_id, paper_id, digest, owner, temporary=temporary)
        text = extract_text(completed, options.output_dir / "text")
        store.record_extraction(job_id, paper_id, digest,
            {"quality": text.reason_code if isinstance(text, AttemptOutcome) else "text_extracted_layout_unverified",
             "path": None if isinstance(text, AttemptOutcome) else str(text)}, owner)
        return 0 if analysis_allowed(validation, options) else 2
    finally:
        if temporary and not staged:
            temporary.unlink(missing_ok=True)
        store.release_lease(job_id, owner)
        write_report(job_id, store, options.output_dir)
