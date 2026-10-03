"""Install only the skill bundled with this exact package build."""
import os
import re
import shutil
from importlib.metadata import version
from pathlib import Path


def bundle() -> Path:
    installed = Path(__file__).parent / "skill"
    return installed if installed.is_dir() else Path(__file__).resolve().parents[2] / "skills" / "paper-access"


def skill_status() -> dict:
    path = bundle() / "SKILL.md"
    match = re.search(r'^  version: "([^"]+)"$', path.read_text(), re.M) if path.is_file() else None
    skill_version = match[1] if match else None
    return {"version": skill_version, "compatible": skill_version == version("paper-access")}


def install_skill(destination: Path | None = None) -> Path:
    if not skill_status()["compatible"]:
        raise ValueError("bundled skill and tool versions differ")
    destination = (destination or Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "skills" / "paper-access").expanduser().resolve()
    source = bundle()
    if destination.exists():
        expected = {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}
        actual = {p.relative_to(destination): p.read_bytes() for p in destination.rglob("*") if p.is_file()}
        if actual == expected:
            return destination
        raise ValueError("skill destination contains different files; preserve or move it before installing")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    return destination
