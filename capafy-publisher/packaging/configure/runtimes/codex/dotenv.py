from __future__ import annotations

from pathlib import Path

from packaging.configure.dotenv import iter_dotenv_assignments
from packaging.configure.sensitive.literals import looks_like_platform_managed_placeholder_value


def dotenv_has_any_value(file_path: Path, expected_value: str) -> bool:
    if not expected_value or not file_path.is_file():
        return False
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        return False
    for _key, value, _line_number in iter_dotenv_assignments(text):
        if value == expected_value:
            return True
    return False


def dotenv_has_key_value(file_path: Path, key_fields: frozenset[str]) -> bool:
    if not file_path.is_file():
        return False
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        return False
    for key, value, _line_number in iter_dotenv_assignments(text):
        if key not in key_fields:
            continue
        if value and not looks_like_platform_managed_placeholder_value(value):
            return True
    return False


__all__ = [
    "dotenv_has_any_value",
    "dotenv_has_key_value",
]
