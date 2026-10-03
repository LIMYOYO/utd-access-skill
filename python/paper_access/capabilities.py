"""Explicit enabled/disabled source capability registry."""
import json
from pathlib import Path


def capabilities():
    local=Path(__file__).parent/"provider-capabilities.json"
    path=local if local.is_file() else Path(__file__).resolve().parents[2]/"profiles/providers/capabilities.json"
    return json.loads(path.read_text())
