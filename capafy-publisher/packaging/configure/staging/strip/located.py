from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Optional

from packaging._shared.config_files.dotenv import find_dotenv_value_span
from packaging._shared.config_files.json_io import find_json_string_value_span
from packaging._shared.config_files.toml_loader import find_toml_value_span
from packaging.configure.staging.strip.targets import StripTarget


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
    return find_dotenv_value_span(
        text,
        field=target.field,
        expected_value=target.value,
        occurrence_index=target.occurrence_index,
        line_number=target.line_number,
        allow_structured_assignment=True,
    )


def _json_value_span(text: str, target: StripTarget) -> Optional[tuple[int, int]]:
    pointer = target.json_pointer
    if not pointer:
        return None
    return find_json_string_value_span(text, pointer, target.value)


def _toml_value_span(text: str, target: StripTarget) -> Optional[tuple[int, int]]:
    target_section = target.toml_section
    if not target_section or not target.field:
        return None
    return find_toml_value_span(
        text,
        section=target_section,
        field=target.field,
        expected_value=target.value,
    )


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


__all__ = ["LocatedReplacementSummary", "replace_located_strip_targets"]
