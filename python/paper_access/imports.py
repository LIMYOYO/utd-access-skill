"""Import bibliography records locally without any network requests."""

import csv
import io
import re
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import bibtexparser
import rispy

from .models import ImportIssue, PaperInput, SourceRef


def normalize_identifier(value: str) -> tuple[str, str] | None:
    value = value.strip()
    if value.lower().startswith(("https://", "http://")):
        try:
            url = urlsplit(value)
        except ValueError:
            return None
        host = (url.hostname or "").lower()
        path = unquote(url.path).strip("/")
        if host in {"doi.org", "dx.doi.org"}:
            value = path
        elif host in {"ssrn.com", "www.ssrn.com", "papers.ssrn.com"}:
            number = parse_qs(url.query).get("abstract_id", [""])[0]
            if not number:
                number = path.removeprefix("abstract=")
            return ("ssrn", number) if number.isdigit() else None
        elif host in {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}:
            value = "arxiv:" + re.sub(r"^(abs|pdf)/", "", path).removesuffix(".pdf")
        elif host in {"nber.org", "www.nber.org"} and path.startswith("papers/"):
            value = "nber:" + path[7:]
        else:
            return None
    value = re.sub(r"^doi\s*:\s*", "", value, flags=re.I)
    value = value.lstrip("(\"'").rstrip(".,;\"'")
    while value.endswith(")") and value.count(")") > value.count("("):
        value = value[:-1]
    if re.fullmatch(r"10\.\d{4,9}/\S+", value, re.I):
        value = value.lower()
        ssrn = re.fullmatch(r"10\.2139/ssrn\.(\d+)", value)
        return ("ssrn", ssrn[1]) if ssrn else ("doi", value)
    arxiv = re.fullmatch(r"(?:arxiv:)?((?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v[1-9]\d*)?)", value, re.I)
    if arxiv:
        return "arxiv", arxiv[1]
    ssrn = re.fullmatch(r"ssrn:(\d+)", value, re.I)
    if ssrn:
        return "ssrn", ssrn[1]
    nber = re.fullmatch(r"(?:nber:)?([wh]\d{4,6})", value, re.I)
    if nber:
        return "nber", nber[1].lower()
    if re.fullmatch(r"RePEc:[^\s:]+:[^\s:]+:[^\s]+", value, re.I):
        return "repec", "RePEc:" + value[6:]
    return None


def _record(fields: dict, source: SourceRef) -> PaperInput:
    identifier = str(fields.get("doi") or fields.get("identifier") or "").strip()
    title = str(fields.get("title") or "").strip()
    normalized = normalize_identifier(identifier) if identifier else None
    if identifier and not normalized:
        raise ValueError("invalid identifier")
    if not normalized:
        url_id = normalize_identifier(str(fields.get("url") or ""))
        normalized = url_id or (("title", title) if title else None)
    if not normalized:
        raise ValueError("missing identifier and title")
    authors = fields.get("authors") or fields.get("author") or ()
    if isinstance(authors, str):
        authors = tuple(a.strip() for a in re.split(r"\s+and\s+|;", authors) if a.strip())
    year = str(fields.get("year") or "").strip()
    if year and not re.fullmatch(r"\d{4}(?:/\d{1,2}(?:/\d{1,2})?)?", year):
        raise ValueError("invalid year")
    return PaperInput(*normalized, (source,), title, tuple(authors), int(year[:4]) if year else None)


def import_records(path: Path) -> tuple[list[PaperInput], list[ImportIssue]]:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in {".txt", ".csv", ".bib", ".ris"}:
        raise ValueError(f"unsupported input format: {suffix}")
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines(keepends=True)
    papers: list[PaperInput] = []
    issues: list[ImportIssue] = []
    by_identifier: dict[tuple[str, str], int] = {}

    def issue(line: int, raw: str, reason: str) -> None:
        issues.append(ImportIssue(str(path), line, raw, reason))

    def add(fields: dict, line: int, raw: str) -> None:
        try:
            paper = _record(fields, SourceRef(str(path), line, raw))
        except ValueError as exc:
            issue(line, raw, str(exc))
            return
        key = paper.identifier_kind, paper.identifier
        if paper.identifier_kind != "title" and key in by_identifier:
            i = by_identifier[key]
            previous = papers[i]
            papers[i] = replace(previous, sources=previous.sources + paper.sources,
                                title=previous.title or paper.title,
                                authors=previous.authors or paper.authors,
                                year=previous.year or paper.year)
        else:
            by_identifier[key] = len(papers)
            papers.append(paper)

    if suffix == ".txt":
        for number, raw_line in enumerate(lines, 1):
            raw = raw_line.rstrip("\r\n")
            value = raw.strip()
            if not value or value.startswith("#"):
                continue
            if normalize_identifier(value):
                add({"identifier": value}, number, raw)
            elif value.lower().startswith(("10.", "doi:", "http:", "https:", "arxiv:", "ssrn:", "repec:", "nber:")) or not any(c.isalpha() for c in value):
                issue(number, raw, "invalid identifier")
            else:
                add({"title": value}, number, raw)
    elif suffix == ".csv":
        reader = csv.DictReader(io.StringIO(text), strict=True)
        if reader.fieldnames is None:
            return [], []
        reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]
        end = reader.line_num
        while True:
            start = end + 1
            try:
                fields = next(reader)
            except StopIteration:
                break
            except csv.Error:
                issue(start, "".join(lines[start - 1:reader.line_num]).rstrip("\r\n"), "malformed CSV record")
                end = reader.line_num
                continue
            end = reader.line_num
            while start < end and not lines[start - 1].rstrip("\r\n"):
                start += 1
            raw = "".join(lines[start - 1:end]).rstrip("\r\n")
            if None in fields or any(v is None for v in fields.values()):
                issue(start, raw, "CSV column count differs from header")
            else:
                add(fields, start, raw)
    elif suffix == ".bib":
        library = bibtexparser.parse_string(text)
        for entry in library.entries:
            add({f.key.lower(): f.value for f in entry.fields}, entry.start_line + 1, entry.raw)
        for block in library.failed_blocks:
            issue(block.start_line + 1, block.raw, "malformed BibTeX block")
    else:
        # Frame records before parsing so one missing ER cannot consume the next TY.
        block: list[str] = []
        start = 1
        for number, line in enumerate(lines, 1):
            if line.startswith("TY  -"):
                if block:
                    issue(start, "".join(block), "RIS record missing ER")
                block, start = [line], number
            elif block:
                block.append(line)
                if line.startswith("ER  -"):
                    raw = "".join(block)
                    try:
                        records = rispy.loads(raw)
                    except (ValueError, KeyError, IndexError):
                        issue(start, raw, "malformed RIS record")
                    else:
                        if len(records) != 1:
                            issue(start, raw, "malformed RIS record")
                        else:
                            record = records[0]
                            add({"doi": record.get("doi"), "url": record.get("url"),
                                 "title": record.get("title") or record.get("primary_title"),
                                 "authors": record.get("authors"),
                                 "year": record.get("year") or record.get("publication_year")}, start, raw)
                    block = []
            elif line.strip():
                issue(number, line.rstrip("\r\n"), "text outside RIS record")
        if block:
            issue(start, "".join(block), "RIS record missing ER")
    papers.sort(key=lambda p: p.sources[0].line)
    issues.sort(key=lambda i: i.line)
    return papers, issues
