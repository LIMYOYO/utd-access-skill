"""Validate file integrity, article identity and evidence of full text separately."""

import hashlib
import re
import unicodedata

from .extract import DOCUMENT_ERRORS, pdf_author_header, read_document
from .imports import normalize_identifier
from .models import Artifact, Candidate, PaperInput, ValidationResult

_ARXIV_STAMP = re.compile(r"arXiv:((?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v[1-9]\d*)?)\s+\[[^\]\r\n]+\]\s+\d{1,2}\s+[A-Za-z]{3}\s+\d{4}", re.I)


def _normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).casefold()
    return "".join(character for character in value if character.isalnum())


def _author_present(author: str, header: str) -> bool:
    def tokens(value):
        value = re.sub(r"(?<=\w)¸\s*(?=\w)", "", value)
        folded = "".join(char for char in unicodedata.normalize("NFKD", value).casefold() if not unicodedata.combining(char))
        return re.findall(r"[^\W\d_]+", folded)
    if "," in author:
        surname, given = author.split(",", 1)
        name = tokens(given) + tokens(surname)
    else:
        name = tokens(author)
    text = tokens(header)
    if not name:
        return False
    # Covers commonly list complete names surname-first without a comma.
    # Require the entire line and all name tokens; never accept a surname
    # substring or an arbitrary permutation spread through surrounding text.
    rotations = [name[offset:] + name[:offset] for offset in range(1, len(name))]
    if any("," not in line and tokens(line) in rotations for line in header.splitlines()):
        return True
    def equivalent(left, right):
        return left == right or (len(left) == 1 and left == right[:1]) or (len(right) == 1 and right == left[:1])
    def middle_matches(left, right):
        if not left:
            return all(len(token) == 1 for token in right)
        if not right:
            return all(len(token) == 1 for token in left)
        if equivalent(left[0], right[0]):
            return middle_matches(left[1:], right[1:])
        if len(left[0]) == len(right[0]) == 1:
            return False  # Explicit conflicting initials cannot both disappear.
        if len(left[0]) == 1:
            return middle_matches(left[1:], right)
        if len(right[0]) == 1:
            return middle_matches(left, right[1:])
        return False
    for start in range(len(text)):
        if len(name) == 1:
            if text[start] == name[0]:
                return True
            continue
        if not equivalent(text[start], name[0]):
            continue
        for stop in range(start + 2, min(len(text), start + len(name) + 4) + 1):
            actual = text[start:stop]
            if actual[-1] == name[-1] and middle_matches(name[1:-1], actual[1:-1]):
                return True
    return False


def _title_present(title: str, document, *, header: str | None = None) -> bool:
    expected = _normalized(title)
    if document.titles:
        return all(_normalized(value) == expected for value in document.titles)
    # PDF text has no semantic title tag. Accept a title only at the start
    # of the document, allowing line wrapping, never as an interior substring.
    lines = [line for line in (document.header if header is None else header).splitlines() if _normalized(line)]
    if lines and re.fullmatch(r"gripspolicyinformationcenterdiscussionpaper\d{2,4}\d{2}", _normalized(lines[0])):
        lines = lines[1:]
    if lines and lines[0].strip() in {"1", "2", "3"}:
        lines = lines[1:]
    # SSRN adds a hosting notice before the title. Skip only this complete,
    # recognizable notice; arbitrary cover text must not enable substring matches.
    if lines and re.fullmatch(r"\s*Electronic copy available at:\s*https?://(?:www\.)?ssrn\.com/abstract=\d+\s*", lines[0], re.I):
        lines = lines[1:]
    if lines and (_ARXIV_STAMP.fullmatch(lines[0].strip()) or lines[0].strip().casefold() in {"invited review", "research article", "review article"}):
        lines = lines[1:]
    for count in range(1, min(len(lines), 10) + 1):
        actual = _normalized(" ".join(lines[:count]))
        if len(actual) >= len(expected):
            return actual == expected
    return False


def validate_artifact(artifact: Artifact, expected: PaperInput, candidate: Candidate) -> ValidationResult:
    try:
        with artifact.path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if artifact.path.stat().st_size != artifact.byte_count or digest != artifact.sha256:
            return ValidationResult("downloaded_unverified", "file_integrity_mismatch")
        document = read_document(artifact)
    except DOCUMENT_ERRORS:
        return ValidationResult("downloaded_unverified", "invalid_document")
    pages = len(document.pages) if document.pages else None
    mime = {"pdf": "application/pdf", "xml": "application/xml", "html": "text/html"}[document.kind]
    front_matter = "\n".join(document.identity_headers) if document.identity_headers else document.header
    if candidate.version == "publishedVersion" and re.search(r"\b(?:accepted\s+manuscript|author'?s?\s+accepted\s+(?:version|manuscript)|preprint|working\s+paper)\b", front_matter, flags=re.I):
        return ValidationResult("ambiguous_match", "version_evidence_conflict", pages=pages, mime_type=mime)
    if not document.text.strip():
        return ValidationResult("downloaded_unverified", "needs_ocr", pages=pages, mime_type=mime, extraction_quality="needs_ocr")
    if re.search(r"\b(?:supplementary\s+(?:material|information)|supporting\s+information|online\s+appendix|electronic\s+companion)\b", front_matter, flags=re.I):
        return ValidationResult("downloaded_unverified", "supplementary_material", pages=pages, mime_type=mime)
    if not document.fulltext_structure or len(document.text.strip()) < 800:
        return ValidationResult("downloaded_unverified", "not_fulltext", pages=pages, mime_type=mime)
    doi = normalize_identifier(expected.doi or "")
    ssrn_expected = re.fullmatch(r"10\.2139/ssrn\.(\d+)", expected.doi or "", re.I)
    identifier_page = "\n".join(document.pages[:max(1, len(document.identity_headers))]) if document.pages else document.header
    ssrn_ids = re.findall(r"^\s*Electronic copy available at:\s*https?://(?:www\.)?ssrn\.com/abstract=(\d+)\s*$", identifier_page, re.I | re.M)
    if ssrn_expected and ssrn_ids and any(value != ssrn_expected[1] for value in ssrn_ids):
        return ValidationResult("ambiguous_match", "primary_identifier_mismatch", pages=pages, mime_type=mime)
    arxiv_ids = [match[1] for line in identifier_page.splitlines() if (match := _ARXIV_STAMP.fullmatch(line.strip()))]
    if expected.identifier_kind == "arxiv" and arxiv_ids:
        def comparable(value):
            return value.casefold() if re.search(r"v\d+$", expected.identifier, re.I) else re.sub(r"v\d+$", "", value, flags=re.I).casefold()
        if any(comparable(value) != comparable(expected.identifier) for value in arxiv_ids):
            return ValidationResult("ambiguous_match", "primary_identifier_mismatch", pages=pages, mime_type=mime)
    matching_arxiv = expected.identifier_kind == "arxiv" and bool(arxiv_ids)
    if expected.identifier_kind == "arxiv" and candidate.provider == "arxiv":
        pinned = normalize_identifier(candidate.location_id)
        if not arxiv_ids:
            return ValidationResult("ambiguous_match", "arxiv_version_unverified", pages=pages, mime_type=mime)
        if not pinned or pinned[0] != "arxiv" or any(value.casefold() != pinned[1].casefold() for value in arxiv_ids):
            return ValidationResult("ambiguous_match", "primary_identifier_mismatch", pages=pages, mime_type=mime)
    evidence = ""
    if document.front_matter_dois and not (doi is None and matching_arxiv) and (doi is None or any(normalize_identifier(value) != doi for value in document.front_matter_dois)):
        return ValidationResult("ambiguous_match", "primary_doi_mismatch", pages=pages, mime_type=mime)
    if ssrn_expected and document.kind == 'pdf':
        from .ssrn_identity import ssrn_identity
        if candidate.paper_id != expected.paper_id:
            return ValidationResult('ambiguous_match','candidate_identity_mismatch',pages=pages,mime_type=mime)
        return ssrn_identity(artifact, expected, document)
    if document.primary_dois:
        if doi is not None and all(normalize_identifier(value) == doi for value in document.primary_dois):
            evidence = "primary_doi"
        elif doi is None and matching_arxiv:
            evidence = "primary_arxiv"
        else:
            return ValidationResult("ambiguous_match", "primary_doi_mismatch", pages=pages, mime_type=mime)
    elif matching_arxiv:
        evidence = "primary_arxiv"
    elif expected.title and expected.authors:
        title = _normalized(expected.title)
        header = document.identity_headers[-1] if document.identity_headers else document.header
        if len(title) >= 12 and _title_present(expected.title, document, header=header):
            if all(_author_present(author, header) for author in expected.authors):
                evidence = "title_and_authors"
            elif document.kind == "pdf":
                geometry_header = pdf_author_header(artifact.path, max(0, len(document.identity_headers) - 1), header)
                if all(_author_present(author, geometry_header) for author in expected.authors):
                    evidence = "title_and_authors_layout"
    if not evidence:
        return ValidationResult("ambiguous_match", "insufficient_identity_evidence", pages=pages, mime_type=mime)
    if candidate.paper_id != expected.paper_id:
        return ValidationResult("ambiguous_match", "candidate_identity_mismatch", pages=pages, mime_type=mime)
    return ValidationResult("verified_fulltext", "verified", evidence, pages, mime, "text_extracted_layout_unverified")


IDENTITY_FAILURES = frozenset({
    'insufficient_identity_evidence', 'anonymous_authors_unverified',
    'primary_identifier_mismatch', 'primary_doi_mismatch', 'arxiv_version_unverified',
})
USABLE_STATUSES = frozenset({'verified_fulltext', 'downloaded_fulltext'})


def assess_artifact(artifact, expected, candidate):
    """Download/body gate first; identity result remains truthful and separate.

    Identity failure codes can only arise after integrity, parse and body checks
    in validate_artifact. Transport association, purpose and version remain guards.
    """
    from dataclasses import replace
    if candidate.paper_id != expected.paper_id:
        return ValidationResult('ambiguous_match', 'candidate_identity_mismatch')
    result = validate_artifact(artifact, expected, candidate)
    if result.reason_code in IDENTITY_FAILURES:
        return replace(result, status='downloaded_fulltext')
    return result


def analysis_allowed(validation, options):
    return validation.status == 'verified_fulltext' or (
        validation.status == 'downloaded_fulltext' and options.validation_policy == 'advisory')
