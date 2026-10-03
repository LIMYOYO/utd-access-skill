"""Deterministic local text extraction; preserves page/paragraph boundaries."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .models import Artifact, AttemptOutcome
from .report import _atomic_text


@dataclass(frozen=True)
class Document:
    kind: str
    text: str
    header: str
    primary_dois: tuple[str, ...]
    titles: tuple[str, ...] = ()
    pages: tuple[str, ...] = ()
    paragraphs: tuple[str, ...] = ()
    fulltext_structure: bool = False
    identity_headers: tuple[str, ...] = ()
    front_matter_dois: tuple[str, ...] = ()


def _tag(element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _text(element) -> str:
    return " ".join(" ".join(element.itertext()).split())


def _at_path(root, path: str) -> list:
    nodes = [root]
    for part in path.split("/"):
        nodes = [child for parent in nodes for child in parent if _tag(child) == part]
    return nodes


def read_document(artifact: Artifact) -> Document:
    with artifact.path.open("rb") as stream:
        leading = stream.read(1024).lstrip()
    if leading.startswith(b"%PDF-"):
        with artifact.path.open("rb") as stream:
            stream.seek(max(0, artifact.path.stat().st_size - 2048))
            if b"%%EOF" not in stream.read():
                raise ValueError("PDF end marker missing")
        # Legacy publisher PDFs often have recoverable producer errors (e.g.
        # duplicate font keys). Identity/body checks still apply after parsing.
        reader = PdfReader(artifact.path, strict=False)
        if reader.is_encrypted or not reader.pages or len(reader.pages) > 2000:
            raise ValueError("encrypted, empty or oversized PDF")
        pages = tuple(page.extract_text() or "" for page in reader.pages)
        full_text = "\n".join(pages)
        body_start = re.search(r"^\s*(?:\d+(?:\.\d+)*[.)]?\s+)?(?:introduction|methods?|model|results?|analysis|conclusions?|discussion|background)\b[^\n]*\n", full_text, flags=re.I | re.M)
        body_text = full_text[body_start.end():] if body_start else ""
        body_text = re.split(r"^\s*(?:references|bibliography)\s*$", body_text, maxsplit=1, flags=re.I | re.M)[0]
        headers = []
        for page in pages[:3]:
            sections = re.split(r"^\s*(?:\d+[.)]?\s+)?(?:abstract|introduction|references|bibliography)\b", page[:4000], maxsplit=1, flags=re.I | re.M)
            headers.append(sections[0])
            catalogue_page = all(re.search(pattern, page, re.I) for pattern in (r"\breport series\b", r"\babstract and keywords\b", r"\bavailability\b"))
            # Continue only across recognizable short repository front matter.
            # An article's abstract/body ends the identity search, even when a
            # later page contains the expected title in a citation.
            if (len(sections) > 1 and not catalogue_page) or len(page) > 4000 or not re.search(r"\b(?:repository|copyright|report|research papers?|working paper|document version)\b", page, re.I):
                break
        header = headers[0]
        doi_matches = tuple(re.findall(r"(?:doi\s*:\s*|doi\.org/)(10\.\d{4,9}/\S+)", headers[-1], flags=re.I))
        front_dois = tuple(value for part in headers for value in re.findall(r"(?:doi\s*:\s*|doi\.org/)(10\.\d{4,9}/\S+)", part, flags=re.I))
        return Document("pdf", full_text, header, doi_matches, pages=pages, fulltext_structure=len(body_text.strip()) >= 800,
                        identity_headers=tuple(headers), front_matter_dois=front_dois)
    mime = artifact.mime_type.split(";", 1)[0].lower()
    if mime in {"application/xml", "text/xml", "application/jats+xml", "application/tei+xml"}:
        root = ElementTree.parse(artifact.path).getroot()
        bodies = [node for node in root.iter() if _tag(node) == "body"]
        headers = [node for node in root.iter() if _tag(node) in {"front", "teiHeader"}]
        dois = []
        titles = []
        for header in headers:
            if _tag(header) == "front":
                ids = _at_path(header, "article-meta/article-id")
                titles.extend(_text(node) for node in _at_path(header, "article-meta/title-group/article-title"))
            else:
                ids = []
                for path in ("fileDesc/publicationStmt/idno", "fileDesc/sourceDesc/biblStruct/idno",
                             "fileDesc/sourceDesc/biblStruct/analytic/idno", "fileDesc/sourceDesc/bibl/idno"):
                    ids.extend(_at_path(header, path))
                titles.extend(_text(node) for node in _at_path(header, "fileDesc/titleStmt/title"))
            dois.extend(_text(node) for node in ids if node.attrib.get("pub-id-type", node.attrib.get("type", "")).lower() == "doi")
        paragraphs = tuple(_text(node) for body in bodies for node in body.iter() if _tag(node) in {"p", "title", "head"})
        return Document("xml", "\n".join(_text(body) for body in bodies), "\n".join(_text(header) for header in headers),
                        tuple(dois), titles=tuple(titles), paragraphs=paragraphs, fulltext_structure=bool(bodies))
    if mime == "text/html":
        soup = BeautifulSoup(artifact.path.read_bytes(), "html.parser")
        if soup.select_one('input[type="password"]'):
            raise ValueError("login form")
        for element in soup(["script", "style", "noscript", "iframe", "nav"]):
            element.decompose()
        article = soup.find("article") or soup.find(id="fulltext") or soup.find(class_="fulltext")
        titles = [node.get("content", "") for node in soup.select('meta[name="citation_title"]')]
        authors = [node.get("content", "") for node in soup.select('meta[name="citation_author"]')]
        dois = tuple(node.get("content", "") for node in soup.select('meta[name="citation_doi"]'))
        h1 = soup.find("h1")
        if h1:
            titles.append(h1.get_text(" ", strip=True))
        header = "\n".join(titles + authors + ([h1.get_text(" ", strip=True)] if h1 else []))
        paragraphs = tuple(node.get_text(" ", strip=True) for node in (article or soup).find_all(["p", "h1", "h2", "h3"]))
        headings = article.find_all(["h2", "h3"]) if article else []
        body_headings = [heading for heading in headings if re.search(r"\b(introduction|methods?|model|results?|analysis|conclusions?|discussion)\b", heading.get_text(" "), re.I)]
        body_text = ""
        if body_headings:
            from bs4 import NavigableString
            body_text = " ".join(str(node) for node in body_headings[0].next_elements
                                 if isinstance(node, NavigableString) and article in node.parents)
        return Document("html", (article or soup).get_text(" ", strip=True), header, dois,
                        titles=tuple(titles), paragraphs=paragraphs, fulltext_structure=len(body_text.strip()) >= 800)
    raise ValueError("unsupported document format or missing PDF signature")


def pdf_author_header(path: Path, page_number: int, raw_header: str) -> str:
    """Alternative author evidence; replace small raised markers, keep raw text.

    Used only after the ordinary title check, on the same article page. The
    geometry is never used to rewrite titles, identifiers or extracted content.
    """
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTChar, LTTextContainer, LTTextLine
    from pdfminer.pdfexceptions import PDFException

    result = raw_header
    try:
        for page in extract_pages(path, page_numbers={page_number}, maxpages=page_number + 1):
            for box in page:
                if not isinstance(box, LTTextContainer):
                    continue
                for line in box:
                    if not isinstance(line, LTTextLine):
                        continue
                    chars = [char for char in line if isinstance(char, LTChar) and char.get_text().strip()]
                    if not chars:
                        continue
                    # Median prevents one larger decorative character from
                    # turning all normal letters into putative superscripts.
                    size = sorted(char.size for char in chars)[len(chars) // 2]
                    baseline_chars = [char for char in chars if char.size >= size * .9]
                    baseline = sorted(char.y0 for char in baseline_chars)[len(baseline_chars) // 2]
                    text = "".join(" " if isinstance(char, LTChar) and char.size < size * .8
                                   and char.y0 > baseline + size * .15
                                   and re.fullmatch(r"[a-z0-9*]", char.get_text()) else char.get_text()
                                   for char in line)
                    original = line.get_text()
                    if original != text:
                        # Match the original line inside the already bounded
                        # header. Layout cannot promote body/citation text.
                        pattern = r"\s+".join(re.escape(word) for word in original.split())
                        if pattern:
                            result = re.sub(r"(?<!\w)" + pattern + r"(?!\w)", lambda _: text, result)
    except (PDFException, OSError, ValueError, UnicodeError):
        return ""
    return result


DOCUMENT_ERRORS = (OSError, ValueError, PdfReadError, DefusedXmlException, ElementTree.ParseError, UnicodeError)


def extract_text(artifact: Artifact, output_dir: Path) -> Path | AttemptOutcome:
    try:
        document = read_document(artifact)
    except DOCUMENT_ERRORS:
        return AttemptOutcome("downloaded_unverified", artifact.provider, "text_extraction_failed")
    if not document.text.strip():
        return AttemptOutcome("downloaded_unverified", artifact.provider, "needs_ocr")
    result = {"sha256": artifact.sha256, "quality": "text_extracted_layout_unverified",
              "text": document.text,
              "pages": [{"page": number, "text": text} for number, text in enumerate(document.pages, 1)],
              "paragraphs": [{"paragraph": number, "text": text} for number, text in enumerate(document.paragraphs, 1)]}
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{artifact.sha256}.json"
    _atomic_text(path, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return path
