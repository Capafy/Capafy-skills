from __future__ import annotations

import re
from typing import Optional

from packaging.common.text_parse import strip_wrapping_quotes

try:
    import tomllib  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - Python 3.8-3.10
    from packaging.common import minimal_toml as tomllib  # type: ignore[no-redef]


_TOML_SECTION_RE = re.compile(r"^\s*\[([^\[\]]+)\]\s*(?:#.*)?$")
_TOML_KEY_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*=")


def safe_toml_loads(text: str) -> dict:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        if normalized == text:
            raise
        return tomllib.loads(normalized)


def _split_toml_path(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in str(value or "").strip().split(".") if part.strip())


def _toml_key_path_from_assignment_key(
    current_section: tuple[str, ...],
    assignment_key: str,
) -> tuple[tuple[str, ...], str]:
    key_parts = _split_toml_path(assignment_key)
    if not key_parts:
        return (), ""
    if current_section or len(key_parts) == 1:
        return current_section, key_parts[-1]
    return key_parts[:-1], key_parts[-1]


def find_toml_value_span(
    text: str,
    *,
    section: str = "",
    field: str,
    expected_value: str,
) -> Optional[tuple[int, int]]:
    target_section = _split_toml_path(section)
    target_field = str(field or "").strip()
    target_value = str(expected_value or "").strip()
    if not target_field or not target_value:
        return None

    current_section: tuple[str, ...] = ()
    offset = 0
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        line_offset = offset
        offset += len(raw_line)
        section_match = _TOML_SECTION_RE.match(line)
        if section_match:
            current_section = _split_toml_path(section_match.group(1).strip())
            continue
        key_match = _TOML_KEY_RE.match(line)
        if not key_match:
            continue
        assignment_section, assignment_field = _toml_key_path_from_assignment_key(
            current_section,
            key_match.group(1).strip(),
        )
        if assignment_section != target_section or assignment_field != target_field:
            continue
        value_start, value_end, value_text = _toml_assignment_value_span(line, key_match.end(1))
        if strip_wrapping_quotes(value_text) != target_value:
            continue
        return line_offset + value_start, line_offset + value_end
    return None


def _toml_assignment_value_span(line: str, key_end: int) -> tuple[int, int, str]:
    equals_index = line.find("=", key_end)
    if equals_index < 0:
        return len(line), len(line), ""
    raw_value = line[equals_index + 1 :]
    value_start = equals_index + 1 + len(raw_value) - len(raw_value.lstrip())
    value_text = raw_value.strip()
    value_end = value_start + len(value_text)
    return value_start, value_end, value_text


__all__ = [
    "find_toml_value_span",
    "safe_toml_loads",
    "tomllib",
]
