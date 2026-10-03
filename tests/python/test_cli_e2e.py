import json
from pathlib import Path
from paper_access.cli import main


def test_doctor_reports_bundled_skill_version(capsys):
    assert main(["doctor", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["skill"]["compatible"] is True
    assert result["skill"]["version"] == result["version"]


def test_skill_install_is_idempotent_and_preserves_unrelated_directory(tmp_path, capsys):
    destination = tmp_path / "skills" / "paper-access"
    assert main(["install-skill", "--destination", str(destination)]) == 0
    assert (destination / "SKILL.md").is_file()
    assert main(["install-skill", "--destination", str(destination)]) == 0
    (destination / "SKILL.md").write_text("User modified skill")
    assert main(["install-skill", "--destination", str(destination)]) == 1
    assert (destination / "SKILL.md").read_text() == "User modified skill"
