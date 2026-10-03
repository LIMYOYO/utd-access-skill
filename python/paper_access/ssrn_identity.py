"""Bounded SSRN front-page identity recognition, separate from other providers."""
import re
from dataclasses import replace
from html import unescape
from bs4 import BeautifulSoup
from .models import ValidationResult

_BODY = re.compile(r'^\s*(?:\d+(?:\.\d+)*[.)]?\s+)?(?:abstract|introduction|references|bibliography|problem\s+definition|methodology)\b', re.I | re.M)
_CATALOGUE = re.compile(r'\brepository\b|\bmetadata record\b|\breport series\b|\bavailability\b', re.I)

def clean_title(value):
    if re.search(r'</?[a-z][^>]*>',value,re.I):value=BeautifulSoup(value,'html.parser').get_text(' ',strip=True)
    return ' '.join(unescape(value).split())

def _repair_accents(value):
    # Only a recognizable detached diacritic between letters can join tokens.
    # Arbitrary spaces, word boundaries and conflicting initials stay intact.
    return re.sub(r'(?<=[^\W\d_])[´`ˆ¨˜ˇ˘¯˚˛\u0300-\u036f][ \t]*(?=[^\W\d_])','',value)

def _headers(document):
    # An abstract/body marks the actual article, including an article whose
    # title happens to contain a repository keyword. Covers never override it.
    for index, page in enumerate(document.pages[:3]):
        match = _BODY.search(page[:6000])
        header = page[:match.start()] if match else page[:6000]
        if match:
            yield index, header
            return
        if _CATALOGUE.search(header):
            continue
        if not re.search(r'working\s+paper|copyright|report', header, re.I):
            yield index, header
            return
    # Only covers within the scan limit: abstain, never fall back to a cover.

def _without_labels(header):
    lines=[line.strip() for line in header.splitlines() if line.strip()]
    journal_label=False
    while lines:
        line=lines[0]
        if re.match(r'^Working Paper is the author[’\x27]s intellectual property\.',line):
            end=next((i for i,value in enumerate(lines[:12]) if re.fullmatch(r'Copyright\s*©?\s*\d{4}\s*INSEAD',value,re.I)),None)
            if end is not None:lines=lines[end+1:];continue
        if re.fullmatch(r'UtilitasMathematica|MANUFACTURING\s*&?\s*SERVICE OPERATIONS MANAGEMENT|MANAGEMENT SCIENCE|OPERATIONS RESEARCH',line,re.I):
            journal_label=True;lines.pop(0);continue
        if re.fullmatch(r'Working Paper|POM Forum|INFORMS',line,re.I):
            lines.pop(0);continue
        if re.fullmatch(r'\d{4}/[A-Z0-9/-]+|\(Revised version of [A-Z0-9/-]+\)',line,re.I):
            lines.pop(0);continue
        if line in ('1','2','3') or (journal_label and re.fullmatch(r'\d{1,4}',line)):
            lines.pop(0);continue
        if re.fullmatch(r'Electronic copy available at:\s*https?://(?:www\.)?ssrn\.com/abstract=\d+',line,re.I):
            lines.pop(0);continue
        if re.match(r'^(?:Vol\.|issn\b|eissn\b|doi\s+10\.|c?©\s*\d|Copyright\s*©?\s*\d)',line,re.I):
            lines.pop(0);continue
        break
    return '\n'.join(lines)

def ssrn_identity(artifact,expected,document):
    from .validate import _author_present, _title_present, _normalized
    from .extract import pdf_author_header
    expected=replace(expected,title=clean_title(expected.title))
    pages=len(document.pages);base={'pages':pages,'mime_type':'application/pdf','extraction_quality':'text_extracted_layout_unverified'}
    # All inspected pages, including skipped covers, retain identifier guards.
    identifier = expected.identifier
    for page in document.pages[:3]:
        ids = re.findall(r'^\s*Electronic copy available at:\s*https?://(?:www\.)?ssrn\.com/abstract=(\d+)\s*$', page, re.I | re.M)
        if any(value != identifier for value in ids):
            return ValidationResult('ambiguous_match', 'primary_identifier_mismatch', **base)
    from .imports import normalize_identifier
    for page in document.pages[:3]:
        boundary = _BODY.search(page[:6000])
        header = page[:boundary.start()] if boundary else page[:6000]
        dois = re.findall(r'(?:doi\s*:\s*|doi\.org/)(10\.\d{4,9}/\S+)', header, re.I)
        if any(normalize_identifier(value) != normalize_identifier(expected.doi) for value in dois):
            return ValidationResult('ambiguous_match', 'primary_doi_mismatch', **base)
        if boundary:
            break
    for index,header in _headers(document):
        bounded=_without_labels(header)
        if len(_normalized(expected.title))<12 or not _title_present(expected.title,document,header=bounded):continue
        if re.search(r"authors?.{0,40}(?:blinded|anonymous)|(?:blinded|anonymous).{0,40}authors?", ' '.join(bounded.split()), re.I):
            return ValidationResult('downloaded_unverified','anonymous_authors_unverified','title_matched_authors_blinded_page_'+str(index+1),**base)
        repaired=_repair_accents(bounded)
        if expected.authors and all(_author_present(author,repaired) for author in expected.authors):
            return ValidationResult('verified_fulltext','verified','title_and_authors_page_'+str(index+1),**base)
        if expected.authors:
            geometry=_repair_accents(pdf_author_header(artifact.path,index,bounded))
            if all(_author_present(author,geometry) for author in expected.authors):
                return ValidationResult('verified_fulltext','verified','title_and_authors_layout_page_'+str(index+1),**base)
    return ValidationResult('ambiguous_match','insufficient_identity_evidence',**base)
