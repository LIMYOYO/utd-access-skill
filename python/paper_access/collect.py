"""Resumable Crossref journal manifest collection; never downloads full text."""
import csv
import io
import json
import re
import time
import sqlite3
from pathlib import Path
from .imports import normalize_identifier
from .report import _atomic_text


async def collect(http, *, output: Path, **kwargs) -> dict:
    output = Path(output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(output) + ".lock.sqlite3", timeout=0)
    try:
        try:
            db.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as error:
            if "locked" in str(error).lower():
                raise ValueError("this collection already has an active executor") from None
            raise
        return await _collect(http, output=output, **kwargs)
    finally:
        db.rollback()
        db.close()


async def _collect(http, *, issn: str, from_year: int, to_year: int, max_records: int,
                  output: Path, page_size: int = 200) -> dict:
    if not re.fullmatch(r"\d{4}-\d{3}[\dX]", issn, re.I) or not 1000 <= from_year <= to_year <= 2100:
        raise ValueError("invalid ISSN or year range")
    if not 1 <= max_records <= 10000 or not 1 <= page_size <= 1000:
        raise ValueError("max-records must be 1..10000 and page size 1..1000")
    output = Path(output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    state_path = output.with_suffix(output.suffix + ".state.json")
    query = {"issn": issn.upper(), "from_year": from_year, "to_year": to_year, "max_records": max_records}
    state = json.loads(state_path.read_text()) if state_path.exists() else {"query": query, "cursor": "*", "records": [], "issues": [], "pages": [], "exhausted": False}
    if state["query"] != query:
        raise ValueError("existing collection has different parameters; choose another output")
    seen = {row["identifier"] for row in state["records"]}
    url = "https://api.crossref.org/journals/" + query["issn"] + "/works"
    while len(state["records"]) < max_records and not state["exhausted"]:
        size = min(page_size, max_records - len(state["records"]))
        params = {"filter": f"from-pub-date:{from_year}-01-01,until-pub-date:{to_year}-12-31", "rows": size,
                  "cursor": state["cursor"]}
        response = await http.request("GET", url, provider="crossref", params=params)
        if response.status_code != 200:
            raise ValueError(f"collection source returned HTTP {response.status_code}; saved cursor retained")
        try:
            data = response.json()["message"]
            items, next_cursor = data["items"], data["next-cursor"]
            if not isinstance(items, list) or not isinstance(next_cursor, str):
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise ValueError("invalid collection response; saved cursor retained") from None
        added = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                state["issues"].append({"page": len(state["pages"]), "index": index, "reason": "invalid_record"})
                continue
            value = item.get("DOI")
            identity = normalize_identifier(value) if isinstance(value, str) else None
            if not identity or identity[0] not in {"doi", "ssrn"}:
                state["issues"].append({"page": len(state["pages"]), "index": index, "reason": "missing_or_invalid_doi"})
                continue
            doi = value.lower()
            if doi in seen:
                continue
            seen.add(doi)
            titles = item.get("title")
            title = titles[0] if isinstance(titles, list) and titles and isinstance(titles[0], str) else ""
            state["records"].append({"identifier": doi, "title": title})
            added.append(doi)
            if len(state["records"]) == max_records:
                break
        state["pages"].append({"cursor": state["cursor"], "returned": len(items), "added_ids": added, "retrieved_at": time.time()})
        state["exhausted"] = len(items) < size
        if not state["exhausted"] and next_cursor == state["cursor"] and not added:
            raise ValueError("collection cursor made no progress; saved cursor retained")
        state["cursor"] = next_cursor
        _atomic_text(state_path, json.dumps(state, ensure_ascii=False, indent=2))
        if len(state["pages"]) >= 1000 and len(state["records"]) < max_records and not state["exhausted"]:
            raise ValueError("collection exceeded 1000 pages; inspect saved state")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=["identifier", "title"])
    writer.writeheader();writer.writerows(state["records"])
    _atomic_text(output, stream.getvalue())
    return {"count": len(state["records"]), "requested": max_records, "exhausted": state["exhausted"],
            "output": str(output), "state": str(state_path), "issues": len(state["issues"])}
