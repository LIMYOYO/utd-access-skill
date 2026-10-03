"""Command-line interface for the local batch tool."""

import argparse
import asyncio
import json
import platform
import sqlite3
import sys
from decimal import Decimal, InvalidOperation
from importlib.metadata import version
from pathlib import Path

from .config import CredentialResolver, data_directory
from .budget import BudgetLedger
from .http import HttpClient
from .providers.base import AccessContext
from .runner import run_job
from .jobs import plan_job
from .models import JobOptions
from .report import write_report
from .store import JobStore, JobBusy


def main(argv: list[str] | None = None) -> int:
    actual = sys.argv[1:] if argv is None else argv
    if actual and actual[0] == "bridge":
        from .bridge.cli import main as bridge_main
        return bridge_main(actual[1:])
    parser = argparse.ArgumentParser(prog="utd-access-skill")
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="inspect local configuration; makes no network requests")
    doctor.add_argument("--json", action="store_true")
    plan = commands.add_parser("plan", help="import inputs and save an offline task")
    plan.add_argument("input", type=Path)
    plan.add_argument("--out", type=Path, required=True)
    plan.add_argument("--version", choices=["best-available", "published-only"], default="best-available")
    plan.add_argument("--validation-policy", choices=["advisory", "strict"], default="advisory")
    plan.add_argument("--purpose", choices=["reading", "tdm", "ai"], default="reading")
    plan.add_argument("--max-cost-usd", default="0")
    plan.add_argument("--max-file-mib", type=int, default=100)
    plan.add_argument("--institution", type=Path, help="local institution profile JSON")
    manual = commands.add_parser("import-file", help="validate a file obtained through your browser")
    manual.add_argument("job_id")
    manual.add_argument("paper_id")
    manual.add_argument("file", type=Path)
    manual.add_argument("--version", choices=["unknown", "publishedVersion", "acceptedVersion", "submittedVersion"], default="unknown")
    report = commands.add_parser("report", help="write reports from saved task state")
    report.add_argument("job_id")
    report.add_argument("--format", choices=["json", "html", "csv"], default="json")
    metrics = commands.add_parser("metrics", help="summarize coverage against all input rows")
    metrics.add_argument("job_id")
    for action in ("fetch", "resume"):
        command = commands.add_parser(action, help="acquire missing full text and preserve progress")
        command.add_argument("job_id")
    install = commands.add_parser("install-skill", help="install this package's bundled Codex skill")
    install.add_argument("--destination", type=Path)
    collector = commands.add_parser("collect", help="build a resumable journal/year bibliography from Crossref")
    collector.add_argument("--issn", required=True)
    collector.add_argument("--from-year", type=int, required=True)
    collector.add_argument("--to-year", type=int, required=True)
    collector.add_argument("--max-records", type=int, required=True)
    collector.add_argument("--out", type=Path, required=True)
    commands.add_parser("capabilities", help="show enabled routes and unprovisioned source capabilities")
    args = parser.parse_args(argv)
    if args.command == "capabilities":
        from .capabilities import capabilities
        print(json.dumps(capabilities(), ensure_ascii=False))
        return 0
    if args.command == "collect":
        from .collect import collect
        from .http import NetworkFailure
        async def gather():
            async with HttpClient() as http:
                return await collect(http, issn=args.issn, from_year=args.from_year, to_year=args.to_year,
                                     max_records=args.max_records, output=args.out)
        try:
            print(json.dumps(asyncio.run(gather()), ensure_ascii=False))
            return 0
        except (OSError, ValueError, NetworkFailure) as error:
            print(f"utd-access-skill: {error}", file=sys.stderr)
            return 1
    if args.command == "install-skill":
        from .skill import install_skill
        try:
            print(install_skill(args.destination))
            return 0
        except (ValueError, OSError) as error:
            print(f"utd-access-skill: {error}", file=sys.stderr)
            return 1
    if args.command != "doctor":
        try:
            store = JobStore(data_directory() / "jobs.sqlite3")
            exit_code = 0
            if args.command == "plan":
                options = JobOptions(args.out, args.version, args.purpose, Decimal(args.max_cost_usd), args.max_file_mib * 1024 * 1024, json.loads(args.institution.read_text()) if args.institution else None, validation_policy=args.validation_policy)
                job_id = plan_job(args.input, options, store)
            elif args.command == "import-file":
                from .institution import import_file
                job_id = args.job_id
                exit_code = import_file(job_id, args.paper_id, args.file, store, version=args.version)
            elif args.command in {"fetch", "resume"}:
                job_id = args.job_id
                async def execute():
                    async with HttpClient() as http:
                        context = AccessContext(http, BudgetLedger(store), CredentialResolver(), store.options(job_id), job_id)
                        return await run_job(job_id, store, context)
                exit_code = asyncio.run(execute())
            else:
                job_id = args.job_id
                write_report(job_id, store, store.options(job_id).output_dir)
            snapshot = store.snapshot(job_id)
            if args.command == "metrics":
                from .benchmark import summarize_job
                print(json.dumps(summarize_job(job_id, store), ensure_ascii=False))
                return 0
            if args.command == "report" and args.format != "json":
                print(store.options(job_id).output_dir / f"report.{args.format}")
            else:
                print(json.dumps(snapshot, ensure_ascii=False))
            return exit_code
        except (OSError, ValueError, KeyError, InvalidOperation, sqlite3.Error, JobBusy) as exc:
            print(f"utd-access-skill: {exc}", file=sys.stderr)
            return 1
    from .skill import skill_status
    credentials = CredentialResolver()
    result = {"version": version("utd-access-skill"), "python": platform.python_version(),
              "data_dir": str(data_directory()),
              "credentials": {provider: "configured" if credentials.get(provider, key) else "missing"
                              for provider, key in credentials.VARIABLES},
              "network_probed": False, "skill": skill_status()}
    print(json.dumps(result, ensure_ascii=False, indent=None if args.json else 2))
    return 0
