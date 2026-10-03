"""Run against an installed wheel, outside the repository (macOS/Linux)."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def child():
    import httpx
    import paper_access.cli as cli
    from paper_access.http import HttpClient
    async def public(host):
        return ["93.184.216.34"]
    def respond(request):
        if os.environ.get("SMOKE_NO_NETWORK"):
            raise AssertionError("resume contacted the network for a verified file")
        if "api.openalex.org" == request.headers["host"]:
            if "ssrn" in request.url.path:
                return httpx.Response(403)
            return httpx.Response(200, json={"doi": "10.1234/queues", "locations": [{"id": "fixture:one", "is_oa": True,
                "pdf_url": "https://repo.example/fulltext", "version": "acceptedVersion"}]})
        if "api.crossref.org" == request.headers["host"]:
            doi = "10.2139/ssrn.12345" if "ssrn" in request.url.path else "10.1234/queues"
            return httpx.Response(200, json={"message": {"DOI": doi, "title": ["Queueing and Service Systems"],
                "author": [{"given": "Jane", "family": "Smith"}], "published": {"date-parts": [[2024]]}}})
        body = '<article><front><article-meta><article-id pub-id-type="doi">10.1234/queues</article-id></article-meta></front><body><sec><title>Introduction</title><p>' + 'Service capacity determines delays. ' * 40 + '</p></sec></body></article>'
        return httpx.Response(200, headers={"content-type": "application/xml"}, content=body.encode())
    cli.HttpClient = lambda: HttpClient(transport=httpx.MockTransport(respond), resolver=public)
    return cli.main(sys.argv[2:])


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        env = dict(os.environ, PAPER_ACCESS_DATA_DIR=str(root / "state"))
        env.pop("UNPAYWALL_EMAIL", None)
        env.pop("OPENALEX_API_KEY", None)
        def run(*args, expected=0, no_network=False):
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "child", *map(str, args)],
                                    cwd=root, env=dict(env, **({"SMOKE_NO_NETWORK": "1"} if no_network else {})), capture_output=True, text=True)
            assert result.returncode == expected, (args, result.returncode, result.stderr)
            return json.loads(result.stdout)
        doctor = run("doctor", "--json")
        assert doctor["skill"]["compatible"]
        references = root / "single.txt"
        references.write_text("10.1234/queues\n")
        plan = run("plan", references, "--out", root / "single")
        done = run("fetch", plan["job_id"])
        assert done["verified_count"] == 1
        resumed = run("resume", plan["job_id"], no_network=True)
        assert len(resumed["attempts"]) == len(done["attempts"])
        bib = root / "batch.bib"
        bib.write_text('@article{one,doi={10.1234/queues}}\n@article{two,doi={10.2139/ssrn.12345}}')
        batch = run("plan", bib, "--out", root / "batch")
        partial = run("fetch", batch["job_id"], expected=2)
        assert partial["verified_count"] == 1 and len(partial["papers"]) == 2
        strict = run("plan", references, "--out", root / "strict", "--version", "published-only", "--max-cost-usd", "0")
        rejected = run("fetch", strict["job_id"], expected=2)
        assert rejected["verified_count"] == 0
        report = run("report", batch["job_id"], "--format", "json")
        assert report["verified_count"] == 1
        print(json.dumps({"platform": sys.platform, "python": sys.version.split()[0], "package_version": doctor["version"],
                          "passed": ["installed_doctor", "single_doi_fulltext", "resume_no_network", "bibtex_partial_ssrn", "published_only_zero_budget", "report"]}))


if __name__ == "__main__":
    raise SystemExit(child() if len(sys.argv) > 1 and sys.argv[1] == "child" else main())
