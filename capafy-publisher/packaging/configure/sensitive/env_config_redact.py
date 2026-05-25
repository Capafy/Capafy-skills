from __future__ import annotations

from pathlib import Path

from packaging._shared.common.constants import STRUCTURED_ASSIGNMENT_PATTERNS
from packaging._shared.common.local_path_detection import LOCAL_PATH_PLACEHOLDER, looks_like_local_path
from packaging.configure.sensitive.literals import strip_literal_value
from packaging.configure.sensitive.redact_helpers import placeholder_literal, split_raw_line


def redact_env_stage_config(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    redactions = 0
    updated_lines: list[str] = []
    assignment_pattern = STRUCTURED_ASSIGNMENT_PATTERNS[0]
    for raw_line in text.splitlines(keepends=True):
        line, newline = split_raw_line(raw_line)
        match = assignment_pattern.match(line)
        if not match:
            updated_lines.append(line + newline)
            continue
        value = strip_literal_value(match.group("value"))
        if not value or not looks_like_local_path(value):
            updated_lines.append(line + newline)
            continue
        replacement = placeholder_literal(match.group("value"), LOCAL_PATH_PLACEHOLDER)
        value_start = match.start("value")
        value_end = match.end("value")
        updated_lines.append(f"{line[:value_start]}{replacement}{line[value_end:]}{newline}")
        redactions += 1

    if redactions:
        path.write_text("".join(updated_lines), encoding="utf-8")
    return redactions


__all__ = [
    "redact_env_stage_config",
]
