"""Local task creation; discovery and downloading belong to the runner."""

from pathlib import Path

from .imports import import_records
from .models import JobOptions
from .report import write_report
from .store import JobStore


def plan_job(path: Path, options: JobOptions, store: JobStore) -> str:
    inputs, issues = import_records(path)
    if not inputs and not issues:
        raise ValueError("input contains no records")
    job_id = store.create(inputs, issues, options)
    write_report(job_id, store, options.output_dir)
    return job_id
