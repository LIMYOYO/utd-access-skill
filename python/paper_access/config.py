"""Local configuration. Credential values never appear in diagnostics."""

import os
import sys
from pathlib import Path


def data_directory() -> Path:
    override = os.environ.get("PAPER_ACCESS_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "paper-access"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "paper-access"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "paper-access"


class CredentialResolver:
    """Read only the explicitly named service variables."""

    VARIABLES = {("openalex", "api_key"): "OPENALEX_API_KEY",
                 ("unpaywall", "email"): "UNPAYWALL_EMAIL"}

    def get(self, provider: str, key_name: str) -> str | None:
        variable = self.VARIABLES.get((provider, key_name))
        return (os.environ.get(variable, "").strip() or None) if variable else None
