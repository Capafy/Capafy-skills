from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def clone_json_value(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): clone_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clone_json_value(item) for item in value]
    return value


__all__ = ["clone_json_value", "load_json_object"]
