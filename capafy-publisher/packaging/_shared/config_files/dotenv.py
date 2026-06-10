from __future__ import annotations

from collections.abc import Collection, Iterator
import re
from typing import Optional

from packaging._shared.common.constants import STRUCTURED_ASSIGNMENT_PATTERNS


_ENV_LINE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
_ENV_VALUE_LINE = re.compile(r"^(\s*(?:export\s+)?)([A-Za-z_][A-Za-z0-9_]*)(\s*=\s*)(.*)$")


def unquote_dotenv_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value.strip()


def iter_dotenv_assignments(text: str) -> Iterator[tuple[str, str, int]]:
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _ENV_LINE.match(line)
        if not match:
            continue
        yield match.group(1), unquote_dotenv_value(match.group(2)), line_number


def find_dotenv_key_containing_value(text: str, needle: str) -> str:
    target = str(needle or "").strip()
    if not target:
        return ""
    for key, value, _line_number in iter_dotenv_assignments(text):
        if target in value:
            return key
    return ""


def remove_dotenv_key_containing_value_text(text: str, needle: str) -> tuple[str, bool]:
    key = find_dotenv_key_containing_value(text, needle)
    if not key:
        return text, False
    return remove_dotenv_keys_text(text, [key])


def find_dotenv_value_span(
    text: str,
    *,
    field: str = "",
    expected_value: str,
    occurrence_index: int = 0,
    line_number: int = 0,
    allow_structured_assignment: bool = False,
) -> Optional[tuple[int, int]]:
    target_value = str(expected_value or "").strip()
    if not target_value:
        return None
    target_field = str(field or "").strip()
    target_occurrence = occurrence_index if occurrence_index > 0 else 1
    offset = 0
    seen = 0
    for current_line_number, raw_line in enumerate(text.splitlines(keepends=True), start=1):
        line = raw_line.rstrip("\r\n")
        line_offset = offset
        offset += len(raw_line)
        if line_number > 0 and current_line_number != line_number:
            continue
        assignment = _assignment_value_span(
            line,
            allow_structured_assignment=allow_structured_assignment,
        )
        if assignment is None:
            continue
        assignment_field, raw_value, value_start, value_end = assignment
        if target_field and assignment_field != target_field:
            continue
        if unquote_dotenv_value(raw_value) != target_value:
            continue
        if line_number <= 0:
            seen += 1
            if seen != target_occurrence:
                continue
        return line_offset + value_start, line_offset + value_end
    return None


def replace_dotenv_value_text(
    text: str,
    *,
    field: str = "",
    expected_value: str,
    replacement: str,
    occurrence_index: int = 0,
    line_number: int = 0,
    allow_structured_assignment: bool = False,
) -> str:
    span = find_dotenv_value_span(
        text,
        field=field,
        expected_value=expected_value,
        occurrence_index=occurrence_index,
        line_number=line_number,
        allow_structured_assignment=allow_structured_assignment,
    )
    if span is None:
        return text
    start, end = span
    return f"{text[:start]}{replacement}{text[end:]}"


def _assignment_value_span(
    line: str,
    *,
    allow_structured_assignment: bool,
) -> Optional[tuple[str, str, int, int]]:
    if allow_structured_assignment:
        for pattern in STRUCTURED_ASSIGNMENT_PATTERNS:
            match = pattern.match(line)
            if not match:
                continue
            raw_value = match.group("value")
            return (
                str(match.group("key") or "").strip(),
                raw_value,
                match.start("value"),
                match.end("value"),
            )

    match = _ENV_VALUE_LINE.match(line)
    if not match:
        return None
    return match.group(2), match.group(4), match.start(4), match.end(4)


def remove_dotenv_keys_text(text: str, keys: Collection[str]) -> tuple[str, bool]:
    key_set = set(keys)
    if not key_set:
        return text, False
    changed = False
    updated_lines: list[str] = []
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.strip()
        if line and not line.startswith("#"):
            match = _ENV_LINE.match(line)
            if match and match.group(1) in key_set:
                changed = True
                continue
        updated_lines.append(raw_line)
    return "".join(updated_lines), changed


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
    "find_dotenv_key_containing_value",
    "find_dotenv_value_span",
    "iter_dotenv_assignments",
    "remove_dotenv_key_containing_value_text",
    "remove_dotenv_keys_text",
    "replace_dotenv_value_text",
    "unquote_dotenv_value",
    "upsert_dotenv_key_text",
]
