from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Optional

from packaging._shared.common.constants import STRUCTURED_ASSIGNMENT_PATTERNS
from packaging.configure.staging.strip.targets import StripTarget


_JSON_DECODER = json.JSONDecoder()
_TOML_KEY_VALUE = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_-]*)(\s*=\s*)(.*)$")
_TOML_SECTION = re.compile(r"^\s*\[([^\]]+)\]\s*$")


@dataclass(frozen=True)
class LocatedReplacementSummary:
    total_replacements: int
    matched_files: set[Path]


def replace_located_strip_targets(targets_by_file: dict[Path, list[StripTarget]]) -> LocatedReplacementSummary:
    total = 0
    matched_files: set[Path] = set()
    for file_path, file_targets in targets_by_file.items():
        count = _replace_file_targets(file_path, file_targets)
        if count:
            total += count
            matched_files.add(file_path)
    return LocatedReplacementSummary(total_replacements=total, matched_files=matched_files)


def _replace_file_targets(file_path: Path, targets: list[StripTarget]) -> int:
    if not file_path.is_file():
        return 0
    try:
        text = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0

    replacements: list[tuple[int, int, str]] = []
    seen_spans: set[tuple[int, int]] = set()
    for target in targets:
        replacement = _target_replacement(text, target)
        if replacement is None:
            continue
        start, end, replacement_text = replacement
        span = (start, end)
        if span in seen_spans:
            continue
        seen_spans.add(span)
        replacements.append((start, end, replacement_text))
    if not replacements:
        return 0

    updated = text
    for start, end, placeholder in sorted(replacements, key=lambda item: item[0], reverse=True):
        updated = f"{updated[:start]}{placeholder}{updated[end:]}"
    if updated == text:
        return 0
    file_path.write_text(updated, encoding="utf-8")
    return len(replacements)


def _target_replacement(text: str, target: StripTarget) -> Optional[tuple[int, int, str]]:
    if target.location_fmt == "dotenv":
        span = _dotenv_value_span(text, target)
        if span is not None:
            return span[0], span[1], target.placeholder
    elif target.location_fmt == "json":
        span = _json_value_span(text, target)
        if span is not None:
            return span[0], span[1], json.dumps(target.placeholder, ensure_ascii=False)
    elif target.location_fmt == "toml":
        span = _toml_value_span(text, target)
        if span is not None:
            return span[0], span[1], json.dumps(target.placeholder, ensure_ascii=False)
    span = _nth_value_span(text, target.value, target.occurrence_index)
    if span is None:
        return None
    return span[0], span[1], target.placeholder


def _dotenv_value_span(text: str, target: StripTarget) -> Optional[tuple[int, int]]:
    offset = 0
    seen = 0
    for line_number, raw_line in enumerate(text.splitlines(keepends=True), start=1):
        line = raw_line.rstrip("\r\n")
        line_offset = offset
        offset += len(raw_line)
        if target.line_number > 0 and line_number != target.line_number:
            continue
        assignment = _assignment_match(line)
        if assignment is None:
            continue
        field, raw_value, value_start, value_end = assignment
        if target.field and field != target.field:
            continue
        if _strip_wrapping_quotes(raw_value.strip()) != target.value:
            continue
        if target.line_number <= 0:
            seen += 1
            if seen != (target.occurrence_index if target.occurrence_index > 0 else 1):
                continue
        return line_offset + value_start, line_offset + value_end
    return None


def _json_value_span(text: str, target: StripTarget) -> Optional[tuple[int, int]]:
    pointer = target.json_pointer
    if not pointer:
        return None
    return _json_pointer_string_span(text, _json_pointer_parts(pointer), target.value)


def _json_pointer_string_span(text: str, parts: list[str], expected_value: str) -> Optional[tuple[int, int]]:
    try:
        return _locate_json_value(text, _skip_json_ws(text, 0), parts, expected_value)
    except (json.JSONDecodeError, IndexError, ValueError):
        return None


def _locate_json_value(text: str, pos: int, parts: list[str], expected_value: str) -> Optional[tuple[int, int]]:
    pos = _skip_json_ws(text, pos)
    if not parts:
        value, end = _JSON_DECODER.raw_decode(text, pos)
        if value == expected_value and isinstance(value, str):
            return pos, end
        return None
    if pos >= len(text):
        return None
    if text[pos] == "{":
        return _locate_json_object_member(text, pos, parts, expected_value)
    if text[pos] == "[":
        return _locate_json_array_item(text, pos, parts, expected_value)
    return None


def _locate_json_object_member(text: str, pos: int, parts: list[str], expected_value: str) -> Optional[tuple[int, int]]:
    target_key = parts[0]
    pos = _skip_json_ws(text, pos + 1)
    while pos < len(text) and text[pos] != "}":
        key, key_end = _JSON_DECODER.raw_decode(text, pos)
        if not isinstance(key, str):
            return None
        colon = _skip_json_ws(text, key_end)
        if colon >= len(text) or text[colon] != ":":
            return None
        value_start = _skip_json_ws(text, colon + 1)
        if key == target_key:
            return _locate_json_value(text, value_start, parts[1:], expected_value)
        _value, value_end = _JSON_DECODER.raw_decode(text, value_start)
        pos = _skip_json_ws(text, value_end)
        if pos < len(text) and text[pos] == ",":
            pos = _skip_json_ws(text, pos + 1)
    return None


def _locate_json_array_item(text: str, pos: int, parts: list[str], expected_value: str) -> Optional[tuple[int, int]]:
    try:
        target_index = int(parts[0])
    except ValueError:
        return None
    pos = _skip_json_ws(text, pos + 1)
    index = 0
    while pos < len(text) and text[pos] != "]":
        if index == target_index:
            return _locate_json_value(text, pos, parts[1:], expected_value)
        _value, value_end = _JSON_DECODER.raw_decode(text, pos)
        pos = _skip_json_ws(text, value_end)
        if pos < len(text) and text[pos] == ",":
            pos = _skip_json_ws(text, pos + 1)
        index += 1
    return None


def _skip_json_ws(text: str, pos: int) -> int:
    while pos < len(text) and text[pos] in " \t\r\n":
        pos += 1
    return pos


def _json_pointer_parts(pointer: str) -> list[str]:
    return [
        part.replace("~1", "/").replace("~0", "~")
        for part in pointer.split("/")
        if part
    ]


def _toml_value_span(text: str, target: StripTarget) -> Optional[tuple[int, int]]:
    target_section = target.toml_section
    if not target_section or not target.field:
        return None

    current_section = ""
    offset = 0
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        base_offset = offset
        offset += len(raw_line)
        section_match = _TOML_SECTION.match(line)
        if section_match:
            current_section = section_match.group(1).strip()
            continue
        if current_section != target_section:
            continue
        kv_match = _TOML_KEY_VALUE.match(line)
        if not kv_match or kv_match.group(2) != target.field:
            continue
        raw_value = kv_match.group(4).strip()
        if _strip_wrapping_quotes(raw_value) != target.value:
            continue
        value_start = len(line) - len(kv_match.group(4)) + _leading_whitespace_len(kv_match.group(4))
        value_end = value_start + len(raw_value)
        return base_offset + value_start, base_offset + value_end
    return None


def _nth_value_span(text: str, value: str, occurrence_index: int) -> Optional[tuple[int, int]]:
    target_occurrence = occurrence_index if occurrence_index > 0 else 1
    start = 0
    seen = 0
    while True:
        index = text.find(value, start)
        if index < 0:
            return None
        seen += 1
        if seen == target_occurrence:
            return index, index + len(value)
        start = index + len(value)


def _assignment_match(line: str) -> Optional[tuple[str, str, int, int]]:
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
    return None


def _strip_wrapping_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1].strip()
    return value.strip()


def _leading_whitespace_len(value: str) -> int:
    return len(value) - len(value.lstrip())


__all__ = ["LocatedReplacementSummary", "replace_located_strip_targets"]
