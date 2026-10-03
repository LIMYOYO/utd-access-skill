"""Reports preserve failed input rows and never treat a link as full text."""

import csv
import html
import io
import json
import os
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile

from .store import JobStore


def _atomic_text(path: Path, text: str) -> None:
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _legacy_artifacts(snapshot: dict) -> dict:
    """Revalidate old artifacts lacking selection metadata without network I/O."""
    from .models import Artifact, Candidate, PaperInput, SourceRef
    from .validate import validate_artifact

    selected = {}
    modern = {item["paper_id"] for item in snapshot["artifacts"] if "active" in item}
    papers = {item["paper_id"]: item for item in snapshot["papers"]}
    for item in snapshot["artifacts"]:
        if item["paper_id"] in modern or item["paper_id"] in selected or "candidate" not in item:
            continue
        source = papers[item["paper_id"]]
        if source["status"] != "verified_fulltext":
            continue
        fields = {key: source[key] for key in PaperInput.__dataclass_fields__ if key in source}
        fields["sources"] = tuple(SourceRef(**row) for row in fields["sources"])
        fields["authors"] = tuple(fields["authors"])
        artifact = Artifact(**{key: Path(item[key]) if key == "path" else item[key]
                               for key in Artifact.__dataclass_fields__ if key in item})
        candidate_fields = dict(item["candidate"])
        candidate_fields["estimated_cost_usd"] = Decimal(candidate_fields["estimated_cost_usd"])
        candidate_fields["usage"] = tuple(candidate_fields["usage"])
        if validate_artifact(artifact, PaperInput(**fields), Candidate(**candidate_fields)).status == "verified_fulltext":
            selected[item["paper_id"]] = item
    return selected


def report_rows(snapshot: dict) -> list[dict]:
    attempts = {}
    for attempt in snapshot["attempts"]:
        attempts.setdefault(attempt["paper_id"], []).append(attempt)
    from .institution import build_access_links
    from .models import PaperInput, SourceRef
    rows = []
    artifacts = {item["paper_id"]: item for item in snapshot["artifacts"] if item.get("active") and item.get("validation", {}).get("status") in {"verified_fulltext", "downloaded_fulltext"}}
    artifacts = {**_legacy_artifacts(snapshot), **artifacts}
    for paper in snapshot["papers"]:
        history = attempts.get(paper["paper_id"], [])
        latest = history[-1] if history else {}
        known_cost = str(sum((Decimal(item["cost_usd"]) for item in history if item.get("cost_usd") is not None), Decimal("0")))
        cost_complete = bool(history) and all(item.get("cost_usd") is not None for item in history)
        artifact = artifacts.get(paper["paper_id"], {}) if paper["status"] in {"verified_fulltext", "downloaded_fulltext"} else {}
        file_path = ""
        if artifact.get("path"):
            try:
                file_path = Path(artifact["path"]).relative_to(snapshot["options"]["output_dir"]).as_posix()
            except ValueError:
                pass
        rows.append({"paper_id": paper["paper_id"], "identifier": paper["identifier"], "title": paper["title"],
                     "status": paper["status"], "provider": latest.get("provider", ""),
                     "reason": latest.get("reason_code", ""), "cost_usd": known_cost if cost_complete else None,
                     "known_cost_usd": known_cost, "cost_complete": cost_complete,
                     "access_links": build_access_links(PaperInput(paper["identifier_kind"], paper["identifier"],
                         tuple(SourceRef(**source) for source in paper["sources"]), paper["title"], tuple(paper["authors"]),
                         paper["year"], paper.get("resolved_doi")), snapshot["options"].get("institution")),
                     "sources": paper["sources"], "file": file_path, "version": artifact.get("version", "unknown"),
                     "source_uri": artifact.get("source_uri"),
                     "license": artifact.get("candidate", {}).get("license"),
                     "attempts": [{key: attempt[key] for key in ("status", "provider", "reason_code", "next_retry_at", "cost_usd", "redacted_detail", "created_at")} for attempt in history],
                     "extraction_quality": artifact.get("extraction", {}).get("quality", "not_extracted")})
    for issue in snapshot["issues"]:
        rows.append({"paper_id": "", "identifier": "", "title": "", "status": "invalid_input",
                     "provider": "", "reason": issue["issue"], "cost_usd": None, "known_cost_usd": "0", "cost_complete": False,
                     "sources": [{k: issue[k] for k in ("path", "line", "raw")}], "file": "", "version": "unknown",
                     "license": None, "source_uri": None, "attempts": [], "access_links": [], "extraction_quality": "not_extracted"})
    for row in rows:
        usable = row['status'] in {'verified_fulltext','downloaded_fulltext'} and bool(row['file'])
        row['download_status'] = 'complete' if usable else 'not_complete'
        row['identity_status'] = 'verified' if row['status']=='verified_fulltext' else 'authors_blinded' if row['reason']=='anonymous_authors_unverified' else 'not_verified'
        row['analysis_allowed'] = usable and (row['status']=='verified_fulltext' or snapshot['options'].get('validation_policy','strict')=='advisory')
    return sorted(rows, key=lambda row: row["sources"][0]["line"])


def _csv_text(rows: list[dict]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=["paper_id", "identifier", "title", "status", "provider", "reason", "cost_usd", "known_cost_usd", "cost_complete", "sources", "file", "version", "source_uri", "license", "extraction_quality", "attempts", "access_links", "download_status", "identity_status", "analysis_allowed"])
    writer.writeheader()
    for row in rows:
        escaped = {}
        for key, value in row.items():
            cell = json.dumps(value, ensure_ascii=False) if isinstance(value, list) else str(value) if value is not None else ""
            escaped[key] = "'" + cell if cell.lstrip().startswith(("=", "+", "-", "@")) else cell
        writer.writerow(escaped)
    return stream.getvalue()


def _html_text(rows: list[dict], title: str) -> str:
    body = []
    for row in rows:
        labels = {"verified_fulltext": "已下载，身份核对通过", "downloaded_fulltext": "已下载，身份待核对", "not_found": "暂未找到可用全文", "needs_credentials": "需要来源配置",
                  "needs_login": "需要浏览器登录", "ambiguous_match": "论文身份或版本待确认", "downloaded_unverified": "文件未通过验证",
                  "needs_rights_review": "当前用途尚无权限依据", "queued": "等待处理", "invalid_input": "输入需修正",
                  "rate_limited": "来源限流，稍后续跑", "retryable_failure": "来源暂时失败", "budget_exhausted": "达到费用上限"}
        versions = {"publishedVersion": "正式版", "acceptedVersion": "接受稿", "submittedVersion": "工作论文/预印本", "unknown": "版本未知"}
        values = [row["title"] or row["identifier"] or row["sources"][0]["raw"], labels.get(row["status"], row["status"]),
                  versions.get(row["version"], row["version"])]
        link = f'<a href="{html.escape(row["file"], quote=True)}">打开文件</a>' if row["file"] else ""
        access = " · ".join(f'<a href="{html.escape(item["url"], quote=True)}">{html.escape(item["label"])}</a>' for item in row["access_links"])
        history = "".join(f'<li>{html.escape(item["provider"])}: {html.escape(item["status"])} — {html.escape(item["reason_code"])}; USD {html.escape(str(item["cost_usd"])) if item["cost_usd"] is not None else "unknown"}; {html.escape(item["redacted_detail"])}</li>' for item in row["attempts"])
        details = f'<details><summary>Source attempts ({len(row["attempts"])})</summary><ol>{history}</ol></details>' if history else ""
        body.append(f'<tr data-status="{html.escape(row["status"], quote=True)}">' + "".join(f"<td>{html.escape(str(value))}</td>" for value in values) + f"<td>{link}</td><td>{access}</td><td>{details}</td></tr>")
    return ('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{html.escape(title)}</title><h1>{html.escape(title)}</h1>'
            '<table><thead><tr><th scope="col">论文</th><th scope="col">状态</th><th scope="col">版本</th><th scope="col">文件</th><th scope="col">访问入口</th><th scope="col">详细记录</th></tr></thead>'
            '<tbody>' + "".join(body) + '</tbody></table></html>')


def write_report(job_id: str, store: JobStore, output_dir: Path) -> None:
    snapshot = store.snapshot(job_id)
    rows = report_rows(snapshot)
    pending = [row for row in rows if not row["analysis_allowed"]]
    output_dir.mkdir(parents=True, exist_ok=True)
    _atomic_text(output_dir / "manifest.jsonl", "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    _atomic_text(output_dir / "report.json", json.dumps({**snapshot, "rows": rows}, ensure_ascii=False, indent=2) + "\n")
    for name, selection in (("report", rows), ("pending", pending)):
        _atomic_text(output_dir / f"{name}.csv", _csv_text(selection))
        _atomic_text(output_dir / f"{name}.html", _html_text(selection, f"Paper access {name}: {job_id}"))
