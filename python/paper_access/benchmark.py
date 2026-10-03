"""Coverage summaries with fixed input denominator and explicit unknowns."""
from collections import Counter
from decimal import Decimal
from .report import report_rows


def summarize_job(job_id, store) -> dict:
    snapshot = store.snapshot(job_id)
    rows = report_rows(snapshot)
    verified = [row for row in rows if row["status"] == "verified_fulltext"]
    # Each original input occurrence counts, including invalid and duplicate rows.
    fulfilled_inputs = sum(len(row["sources"]) for row in verified)
    total = snapshot["input_count"]
    timings = sorted(event["elapsed_seconds"] for event in store.request_events(job_id))
    def percentile(fraction):
        index = (len(timings) - 1) * fraction
        lower = int(index)
        return timings[lower] + (timings[min(lower + 1, len(timings) - 1)] - timings[lower]) * (index - lower)
    latency = {"count": len(timings), "p50": percentile(.5), "p95": percentile(.95)} if timings else None
    return {"job_id": job_id, "total_inputs": total, "unique_papers": len(snapshot["papers"]),
            "invalid_inputs": len(snapshot["issues"]), "verified": len(verified),
            "fulfilled_inputs": fulfilled_inputs, "coverage": fulfilled_inputs / total if total else 0,
            "versions": dict(Counter(row["version"] for row in verified)),
            "statuses": dict(Counter(row["status"] for row in rows)),
            "reasons": dict(Counter(row["reason"] for row in rows if row["status"] != "verified_fulltext")),
            "extraction": dict(Counter(row["extraction_quality"] for row in verified)),
            "manual_attempts": sum(attempt["provider"] == "manual" for attempt in snapshot["attempts"]),
            "known_cost_usd": str(sum((Decimal(row["known_cost_usd"]) for row in rows), Decimal("0"))),
            "cost_complete": bool(rows) and all(row["cost_complete"] for row in rows),
            "request_latency_seconds": latency,
            "latency_note": "Logical HTTP calls include retries/backoff; older runs without events have no latency estimate."}
