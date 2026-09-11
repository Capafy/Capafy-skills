from __future__ import annotations

from collections.abc import Iterator
import re
from typing import Optional

from packaging.common.constants import STRUCTURED_ASSIGNMENT_PATTERNS
from packaging.common.text_parse import strip_wrapping_quotes


_ENV_LINE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
_ENV_VALUE_LINE = re.compile(r"^(\s*(?:export\s+)?)([A-Za-z_][A-Za-z0-9_]*)(\s*=\s*)(.*)$")


unquote_dotenv_value = strip_wrapping_quotes


def iter_dotenv_assignments(text: str) -> Iterator[tuple[str, str, int]]:
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _ENV_LINE.match(line)
        if not match:
            continue
        yield match.group(1), unquote_dotenv_value(match.group(2)), line_number


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


__all__ = [
    "find_dotenv_value_span",
    "iter_dotenv_assignments",
    "unquote_dotenv_value",
]
