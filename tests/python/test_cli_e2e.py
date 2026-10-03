import json
from pathlib import Path
from paper_access.cli import main


def test_doctor_reports_bundled_skill_version(capsys):
    assert main(["doctor", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["skill"]["compatible"] is True
    assert result["skill"]["version"] == result["version"]


def test_skill_install_is_idempotent_and_preserves_unrelated_directory(tmp_path, capsys):
    destination = tmp_path / "skills" / "utd-paper-access"
    assert main(["install-skill", "--destination", str(destination)]) == 0
    assert (destination / "SKILL.md").is_file()
    assert main(["install-skill", "--destination", str(destination)]) == 0
    (destination / "SKILL.md").write_text("User modified skill")
    assert main(["install-skill", "--destination", str(destination)]) == 1
    assert (destination / "SKILL.md").read_text() == "User modified skill"


def test_default_skill_install_uses_utd_name(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    assert main(["install-skill"]) == 0
    expected = tmp_path / "codex" / "skills" / "utd-paper-access"
    assert capsys.readouterr().out.strip() == str(expected)
    assert (expected / "SKILL.md").is_file()
    assert not (tmp_path / "codex" / "skills" / "paper-access").exists()
