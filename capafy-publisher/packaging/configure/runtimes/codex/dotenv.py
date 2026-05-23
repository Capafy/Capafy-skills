from __future__ import annotations

import re
from pathlib import Path

from packaging.configure.sensitive.literals import looks_like_platform_managed_placeholder_value


_ENV_LINE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


def _unquote_dotenv_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value.strip()


def dotenv_has_any_value(file_path: Path, expected_value: str) -> bool:
    if not expected_value or not file_path.is_file():
        return False
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        return False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _ENV_LINE.match(line)
        if not match:
            continue
        if _unquote_dotenv_value(match.group(2)) == expected_value:
            return True
    return False


def dotenv_has_key_value(file_path: Path, key_fields: frozenset[str]) -> bool:
    if not file_path.is_file():
        return False
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        return False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _ENV_LINE.match(line)
        if not match or match.group(1) not in key_fields:
            continue
        value = _unquote_dotenv_value(match.group(2))
        if value and not looks_like_platform_managed_placeholder_value(value):
            return True
    return False


def upsert_dotenv_key_text(text: str, key: str, value: str) -> str:
    lines = text.splitlines(keepends=True)
    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _ENV_LINE.match(line)
        if not match or match.group(1) != key:
            continue
        newline = "\n" if raw_line.endswith("\n") else ""
        lines[index] = f"{key}={value}{newline}"
        return "".join(lines)
    if text and not text.endswith("\n"):
        text += "\n"
    return f"{text}{key}={value}\n"


__all__ = [
    "dotenv_has_any_value",
    "dotenv_has_key_value",
    "upsert_dotenv_key_text",
]
