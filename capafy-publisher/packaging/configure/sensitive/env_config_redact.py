from __future__ import annotations

from pathlib import Path

from packaging._shared.common.constants import STRUCTURED_ASSIGNMENT_PATTERNS
from packaging._shared.common.local_path_detection import LOCAL_PATH_PLACEHOLDER, looks_like_local_path
from packaging.configure.sensitive.literals import strip_literal_value


def redact_env_file(path: Path, source: str | None = None) -> int:
    from packaging.configure.sensitive.config_redact import _build_assignment_placeholder
    from packaging.configure.sensitive.config_redact import _placeholder_literal
    from packaging.configure.sensitive.config_redact import _split_raw_line

    text = path.read_text(encoding="utf-8")
    redactions = 0
    updated_lines: list[str] = []
    relative_source = source or path.name
    assignment_pattern = STRUCTURED_ASSIGNMENT_PATTERNS[0]
    for raw_line in text.splitlines(keepends=True):
        line, newline = _split_raw_line(raw_line)
        match = assignment_pattern.match(line)
        if not match:
            updated_lines.append(line + newline)
            continue
        placeholder = _build_assignment_placeholder(
            match.group("key"),
            match.group("value"),
            source=relative_source,
            source_detail="",
        )
        if not placeholder:
            updated_lines.append(line + newline)
            continue
        value_start = match.start("value")
        value_end = match.end("value")
        replaced = f"{line[:value_start]}{_placeholder_literal(match.group('value'), placeholder)}{line[value_end:]}"
        redactions += 1
        updated_lines.append(replaced + newline)

    if redactions:
        path.write_text("".join(updated_lines), encoding="utf-8")
    return redactions


def redact_env_stage_config(path: Path) -> int:
    from packaging.configure.sensitive.config_redact import _placeholder_literal
    from packaging.configure.sensitive.config_redact import _split_raw_line

    text = path.read_text(encoding="utf-8")
    redactions = 0
    updated_lines: list[str] = []
    assignment_pattern = STRUCTURED_ASSIGNMENT_PATTERNS[0]
    for raw_line in text.splitlines(keepends=True):
        line, newline = _split_raw_line(raw_line)
        match = assignment_pattern.match(line)
        if not match:
            updated_lines.append(line + newline)
            continue
        value = strip_literal_value(match.group("value"))
        if not value or not looks_like_local_path(value):
            updated_lines.append(line + newline)
            continue
        replacement = _placeholder_literal(match.group("value"), LOCAL_PATH_PLACEHOLDER)
        value_start = match.start("value")
        value_end = match.end("value")
        updated_lines.append(f"{line[:value_start]}{replacement}{line[value_end:]}{newline}")
        redactions += 1

    if redactions:
        path.write_text("".join(updated_lines), encoding="utf-8")
    return redactions


__all__ = [
    "redact_env_file",
    "redact_env_stage_config",
]
