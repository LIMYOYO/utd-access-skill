import json
import os
import subprocess
import sys

from paper_access.cli import main


def test_doctor_json_does_not_disclose_credentials_or_create_state(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PAPER_ACCESS_DATA_DIR", str(tmp_path / "not-created"))
    monkeypatch.setenv("OPENALEX_API_KEY", "secret-never-print")
    assert main(["doctor", "--json"]) == 0
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["credentials"]["openalex"] == "configured"
    assert "secret-never-print" not in output
    assert result["data_dir"] == str(tmp_path / "not-created")
    assert not (tmp_path / "not-created").exists()


def test_module_and_installed_entrypoint_work():
    for argv in ([sys.executable, "-m", "paper_access", "doctor", "--json"], ["paper-access", "doctor", "--json"]):
        result = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["version"]


def test_cli_fetch_and_resume_run_real_pipeline_with_transport_fixture(tmp_path, monkeypatch, capsys, pdf_file):
    import httpx
    import paper_access.cli as cli
    from paper_access.http import HttpClient
    payload = pdf_file().path.read_bytes()
    calls = []
    def respond(request):
        calls.append(request.url.path)
        if request.headers["host"] == "api.openalex.org":
            return httpx.Response(200, json={"doi": "https://doi.org/10.1234/queues", "locations": [{"id": "repo:one", "is_oa": True,
                "pdf_url": "https://repo.example/paper.pdf", "version": "acceptedVersion"}]})
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=payload)
    async def public(host):
        return ["93.184.216.34"]
    monkeypatch.setattr(cli, "HttpClient", lambda: HttpClient(transport=httpx.MockTransport(respond), resolver=public))
    monkeypatch.setenv("PAPER_ACCESS_DATA_DIR", str(tmp_path / "state"))
    monkeypatch.delenv("UNPAYWALL_EMAIL", raising=False)
    source = tmp_path / "papers.csv"
    source.write_text("doi,title,authors\n10.1234/queues,Queueing and Service Systems,Jane Smith\n")
    assert main(["plan", str(source), "--out", str(tmp_path / "out")]) == 0
    job = json.loads(capsys.readouterr().out)["job_id"]
    assert main(["fetch", job]) == 0
    assert json.loads(capsys.readouterr().out)["verified_count"] == 1
    calls.clear()
    assert main(["resume", job]) == 0
    assert calls == []


def test_plan_snapshots_configurable_file_size_limit(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PAPER_ACCESS_DATA_DIR", str(tmp_path / "state"))
    source = tmp_path / "papers.txt"; source.write_text("10.1234/one\n")
    assert main(["plan", str(source), "--out", str(tmp_path / "out"), "--max-file-mib", "8"]) == 0
    assert json.loads(capsys.readouterr().out)["options"]["max_file_bytes"] == 8388608
