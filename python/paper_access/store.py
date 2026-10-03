"""Transactional job state. Connections are short lived and safe across processes."""

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from .models import Artifact, AttemptOutcome, Candidate, ImportIssue, JobOptions, PaperInput, SourceRef, ValidationResult


class JobBusy(RuntimeError):
    """Another executor owns the job, or this executor's lease has expired."""


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


class JobStore:
    SCHEMA_VERSION = 3

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            current = db.execute("PRAGMA user_version").fetchone()[0]
            if current > self.SCHEMA_VERSION:
                raise ValueError("unsupported future database schema")
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS request_events (
                    event_id INTEGER PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(job_id),
                    created_at REAL NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS version_relations (
                    left_id TEXT NOT NULL, right_id TEXT NOT NULL, evidence TEXT NOT NULL,
                    created_at REAL NOT NULL, PRIMARY KEY(left_id,right_id,evidence));
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY, created_at REAL NOT NULL, options TEXT NOT NULL,
                    parent_job_id TEXT REFERENCES jobs(job_id), lease_owner TEXT, lease_until REAL);
                CREATE TABLE IF NOT EXISTS papers (
                    job_id TEXT NOT NULL REFERENCES jobs(job_id), paper_id TEXT NOT NULL,
                    ordinal INTEGER NOT NULL, data TEXT NOT NULL, status TEXT NOT NULL,
                    next_retry_at REAL, PRIMARY KEY(job_id,paper_id));
                CREATE TABLE IF NOT EXISTS inputs (
                    job_id TEXT NOT NULL REFERENCES jobs(job_id), ordinal INTEGER NOT NULL,
                    paper_id TEXT, data TEXT NOT NULL, issue TEXT,
                    PRIMARY KEY(job_id,ordinal),
                    FOREIGN KEY(job_id,paper_id) REFERENCES papers(job_id,paper_id));
                CREATE TABLE IF NOT EXISTS candidates (
                    job_id TEXT NOT NULL, paper_id TEXT NOT NULL, candidate_id TEXT NOT NULL,
                    data TEXT NOT NULL, PRIMARY KEY(job_id,paper_id,candidate_id),
                    FOREIGN KEY(job_id,paper_id) REFERENCES papers(job_id,paper_id));
                CREATE TABLE IF NOT EXISTS attempts (
                    attempt_id INTEGER PRIMARY KEY, job_id TEXT NOT NULL, paper_id TEXT NOT NULL,
                    created_at REAL NOT NULL, data TEXT NOT NULL,
                    FOREIGN KEY(job_id,paper_id) REFERENCES papers(job_id,paper_id));
                CREATE TABLE IF NOT EXISTS artifacts (
                    job_id TEXT NOT NULL, paper_id TEXT NOT NULL, sha256 TEXT NOT NULL,
                    data TEXT NOT NULL, PRIMARY KEY(job_id,paper_id,sha256),
                    FOREIGN KEY(job_id,paper_id) REFERENCES papers(job_id,paper_id));
                CREATE TABLE IF NOT EXISTS cost_reservations (
                    request_id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(job_id),
                    upper_bound TEXT NOT NULL, actual_cost TEXT, status TEXT NOT NULL);
            """)
            db.execute(f"PRAGMA user_version={self.SCHEMA_VERSION}")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def record_request_event(self, job_id: str, event: dict) -> None:
        with self.connection() as db:
            db.execute("INSERT INTO request_events(job_id,created_at,data) VALUES(?,?,?)",
                       (job_id, time.time(), encode(event)))

    def request_events(self, job_id: str) -> list[dict]:
        with self.connection() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT data FROM request_events WHERE job_id=? ORDER BY event_id", (job_id,))]

    def create(self, inputs: list[PaperInput], issues: list[ImportIssue], options: JobOptions,
               *, parent_job_id: str | None = None) -> str:
        job_id = uuid4().hex
        with self.connection() as db:
            db.execute("INSERT INTO jobs(job_id,created_at,options,parent_job_id) VALUES(?,?,?,?)",
                       (job_id, time.time(), encode(asdict(options)), parent_job_id))
            lineage = []
            for ordinal, paper in enumerate(inputs):
                db.execute("INSERT INTO papers(job_id,paper_id,ordinal,data,status) VALUES(?,?,?,?,?)",
                           (job_id, paper.paper_id, ordinal, encode(asdict(paper)), "queued"))
                lineage.extend((s.line, paper.paper_id, asdict(s), None) for s in paper.sources)
            lineage.extend((i.line, None, {"path": i.path, "line": i.line, "raw": i.raw}, i.reason) for i in issues)
            for ordinal, (_, paper_id, source, issue) in enumerate(sorted(lineage, key=lambda row: row[0])):
                db.execute("INSERT INTO inputs VALUES(?,?,?,?,?)", (job_id, ordinal, paper_id, encode(source), issue))
        return job_id

    def options(self, job_id: str) -> JobOptions:
        with self.connection() as db:
            row = db.execute("SELECT options FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError("unknown job")
        value = json.loads(row[0])
        value["output_dir"] = Path(value["output_dir"])
        value["max_cost_usd"] = Decimal(value["max_cost_usd"])
        value.setdefault("validation_policy", "strict")  # Existing jobs keep their original contract.
        return JobOptions(**value)

    def snapshot(self, job_id: str) -> dict:
        with self.connection() as db:
            # All report fields come from the same database snapshot.
            db.execute("BEGIN")
            job = db.execute("SELECT job_id,created_at,options,parent_job_id FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if job is None:
                raise KeyError("unknown job")
            result = dict(job)
            result["options"] = json.loads(result["options"])
            result["papers"] = [dict(json.loads(row["data"]), paper_id=row["paper_id"],
                                     status=row["status"], next_retry_at=row["next_retry_at"])
                                for row in db.execute("SELECT * FROM papers WHERE job_id=? ORDER BY ordinal", (job_id,))]
            inputs = db.execute("SELECT * FROM inputs WHERE job_id=? ORDER BY ordinal", (job_id,)).fetchall()
            result["inputs"] = [dict(json.loads(row["data"]), paper_id=row["paper_id"], issue=row["issue"]) for row in inputs]
            result["issues"] = [row for row in result["inputs"] if row["issue"] is not None]
            result["input_count"] = len(inputs)
            result["verified_count"] = sum(p["status"] == "verified_fulltext" for p in result["papers"])
            result["attempts"] = [dict(json.loads(row["data"]), paper_id=row["paper_id"], created_at=row["created_at"])
                                  for row in db.execute("SELECT * FROM attempts WHERE job_id=? ORDER BY attempt_id", (job_id,))]
            result["artifacts"] = [dict(json.loads(row["data"]), paper_id=row["paper_id"], sha256=row["sha256"])
                                   for row in db.execute("SELECT * FROM artifacts WHERE job_id=?", (job_id,))]
        result['downloaded_count'] = sum(p['status'] in {'verified_fulltext','downloaded_fulltext'} for p in result['papers'])
        strict = result['options'].get('validation_policy', 'strict') == 'strict'
        result['analysis_ready_count'] = result['verified_count'] if strict else result['downloaded_count']
        return result

    def record_attempt(self, job_id: str, paper_id: str, outcome: AttemptOutcome, *, owner: str | None = None, preserve_status: bool = False) -> None:
        if outcome.status == "verified_fulltext":
            raise ValueError("verification requires a validated artifact")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if owner is not None:
                self._fence(db, job_id, owner)
            current = db.execute('SELECT status FROM papers WHERE job_id=? AND paper_id=?',(job_id,paper_id)).fetchone()
            preserve_status = preserve_status or (current is not None and current['status'] in {'verified_fulltext','downloaded_fulltext'} and outcome.status != 'queued')
            if preserve_status:
                changed = db.execute("SELECT 1 FROM papers WHERE job_id=? AND paper_id=?", (job_id, paper_id)).fetchone()
            else:
                changed = db.execute("UPDATE papers SET status=?,next_retry_at=? WHERE job_id=? AND paper_id=?",
                                     (outcome.status, outcome.next_retry_at, job_id, paper_id)).rowcount
            if not changed:
                raise KeyError("unknown paper in job")
            db.execute("INSERT INTO attempts(job_id,paper_id,created_at,data) VALUES(?,?,?,?)",
                       (job_id, paper_id, time.time(), encode(asdict(outcome))))

    def pending(self, job_id: str, *, now: float | None = None) -> list[PaperInput]:
        now = time.time() if now is None else now
        options = self.options(job_id)
        excluded = ('verified_fulltext', 'downloaded_fulltext') if options.validation_policy == 'advisory' else ('verified_fulltext', 'verified_fulltext')
        with self.connection() as db:
            rows = db.execute("SELECT data FROM papers WHERE job_id=? AND status NOT IN (?,?) "
                              "AND (next_retry_at IS NULL OR next_retry_at<=?) ORDER BY ordinal", (job_id, *excluded, now)).fetchall()
        result = []
        for row in rows:
            data = json.loads(row[0])
            data["sources"] = tuple(SourceRef(**source) for source in data["sources"])
            data["authors"] = tuple(data["authors"])
            result.append(PaperInput(**data))
        return result

    def record_artifact(self, job_id: str, paper_id: str, artifact: Artifact) -> None:
        """Register a file without claiming its content or identity was verified."""
        with self.connection() as db:
            db.execute("INSERT INTO artifacts(job_id,paper_id,sha256,data) VALUES(?,?,?,?) "
                       "ON CONFLICT(job_id,paper_id,sha256) DO UPDATE SET data=excluded.data",
                       (job_id, paper_id, artifact.sha256, encode(asdict(artifact))))

    @staticmethod
    def _fence(db, job_id: str, owner: str) -> None:
        row = db.execute("SELECT lease_owner,lease_until FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None or row["lease_owner"] != owner or row["lease_until"] <= time.time():
            raise JobBusy("executor lease expired or replaced")

    def update_paper(self, job_id: str, paper: PaperInput, owner: str) -> None:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self._fence(db, job_id, owner)
            if not db.execute("UPDATE papers SET data=? WHERE job_id=? AND paper_id=?", (encode(asdict(paper)), job_id, paper.paper_id)).rowcount:
                raise KeyError("unknown paper")

    def stage_artifact(self, job_id: str, paper_id: str, artifact: Artifact, candidate: Candidate,
                       validation: ValidationResult, owner: str, *, temporary: Path | None = None) -> None:
        if validation.status not in {"verified_fulltext", "downloaded_fulltext"}:
            raise ValueError("only validated files may be staged")
        data = {**asdict(artifact), "candidate": asdict(candidate), "validation": asdict(validation),
                "temporary": str(temporary) if temporary else None, "active": False}
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self._fence(db, job_id, owner)
            db.execute("INSERT INTO artifacts VALUES(?,?,?,?) ON CONFLICT(job_id,paper_id,sha256) DO UPDATE SET data=excluded.data",
                       (job_id, paper_id, artifact.sha256, encode(data)))

    def publish_artifact(self, job_id: str, paper_id: str, digest: str, owner: str,
                         *, temporary: Path | None = None) -> None:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self._fence(db, job_id, owner)
            row = db.execute("SELECT data FROM artifacts WHERE job_id=? AND paper_id=? AND sha256=?", (job_id, paper_id, digest)).fetchone()
            if row is None:
                raise ValueError("artifact was not staged")
            data = json.loads(row[0])
            if data.get("validation", {}).get("status") not in {"verified_fulltext", "downloaded_fulltext"}:
                raise ValueError("artifact lacks validation evidence")
            destination = Path(data["path"])
            if temporary is not None:
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(temporary, destination)
            if not destination.is_file():
                raise ValueError("staged file is missing")
            for other in db.execute("SELECT sha256,data FROM artifacts WHERE job_id=? AND paper_id=?", (job_id, paper_id)).fetchall():
                artifact_data = json.loads(other["data"])
                artifact_data["active"] = other["sha256"] == digest
                db.execute("UPDATE artifacts SET data=? WHERE job_id=? AND paper_id=? AND sha256=?",
                           (encode(artifact_data), job_id, paper_id, other["sha256"]))
            status = data['validation']['status']
            db.execute("UPDATE papers SET status=?,next_retry_at=NULL WHERE job_id=? AND paper_id=?", (status, job_id, paper_id))
            outcome = AttemptOutcome(status, data["provider"], data['validation']['reason_code'])
            db.execute("INSERT INTO attempts(job_id,paper_id,created_at,data) VALUES(?,?,?,?)", (job_id, paper_id, time.time(), encode(asdict(outcome))))

    def record_extraction(self, job_id: str, paper_id: str, digest: str, result: dict, owner: str) -> None:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self._fence(db, job_id, owner)
            row = db.execute("SELECT data FROM artifacts WHERE job_id=? AND paper_id=? AND sha256=?", (job_id, paper_id, digest)).fetchone()
            if row is None:
                raise KeyError("unknown artifact")
            data = json.loads(row[0])
            data["extraction"] = result
            db.execute("UPDATE artifacts SET data=? WHERE job_id=? AND paper_id=? AND sha256=?", (encode(data), job_id, paper_id, digest))

    def acquire_lease(self, job_id: str, *, now: float | None = None, ttl: float = 120) -> str:
        now = time.time() if now is None else now
        if ttl <= 0:
            raise ValueError("lease ttl must be positive")
        token = uuid4().hex
        with self.connection() as db:
            changed = db.execute("UPDATE jobs SET lease_owner=?,lease_until=? WHERE job_id=? "
                                 "AND (lease_until IS NULL OR lease_until<=?)", (token, now + ttl, job_id, now)).rowcount
            if not changed:
                if not db.execute("SELECT 1 FROM jobs WHERE job_id=?", (job_id,)).fetchone():
                    raise KeyError("unknown job")
                raise JobBusy("job already has an active executor")
        return token

    def renew_lease(self, job_id: str, owner: str, *, now: float | None = None, ttl: float = 120) -> None:
        now = time.time() if now is None else now
        if ttl <= 0:
            raise ValueError("lease ttl must be positive")
        with self.connection() as db:
            if not db.execute("UPDATE jobs SET lease_until=? WHERE job_id=? AND lease_owner=? AND lease_until>?",
                              (now + ttl, job_id, owner, now)).rowcount:
                raise JobBusy("executor lease expired or replaced")

    def release_lease(self, job_id: str, owner: str) -> None:
        with self.connection() as db:
            db.execute("UPDATE jobs SET lease_owner=NULL,lease_until=NULL WHERE job_id=? AND lease_owner=?", (job_id, owner))
