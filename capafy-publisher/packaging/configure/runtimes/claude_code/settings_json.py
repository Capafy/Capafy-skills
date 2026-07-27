from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from packaging.configure.config_errors import invalid_json_config_error, invalid_text_config_error
from packaging.configure.runtimes.claude_code.url_proxy_candidates import (
    SETTINGS_SCAN_RELPATHS,
)


SETTINGS_RELPATH = ".claude/settings.json"


def _load_settings_file(path: Path, *, relpath: str, strict: bool = False) -> dict:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return {}
    except json.JSONDecodeError as exc:
        if strict:
            raise invalid_json_config_error("Claude settings", relpath, exc) from exc
        return {}
    if not isinstance(payload, dict):
        if strict:
            raise invalid_text_config_error("Claude settings", "JSON", relpath, "root value is not an object")
        return {}
    return payload


def validate_claude_settings_json(claude_home: Optional[Path]) -> None:
    if claude_home is None:
        return
    for relpath in SETTINGS_SCAN_RELPATHS:
        path = claude_home / Path(relpath).name
        _load_settings_file(path, relpath=relpath, strict=True)


__all__ = [
    "SETTINGS_RELPATH",
    "validate_claude_settings_json",
]
