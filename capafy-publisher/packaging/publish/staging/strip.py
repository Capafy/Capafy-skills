from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from packaging.config.dotenv import find_dotenv_value_span
from packaging.config.json_io import find_json_string_value_span
from packaging.config.toml_loader import find_toml_value_span
from packaging.runtime.contracts import GenericValue
from packaging.publish.reviewed_scan import EXCLUDE_VALUE, REPLACE_WITH_PLACEHOLDER
from packaging.publish.security.sensitive.value_strip import strip_value_from_staging


@dataclass(frozen=True)
class StripTarget:
    value: str
    placeholder: str
    source_relpath: str = ""
    field: str = ""
    source_detail: str = ""
    occurrence_index: int = 0
    location_fmt: str = ""
    line_number: int = 0
    json_pointer: str = ""
    toml_section: str = ""


def collect_generic_strip_targets(generic_values: Iterable[GenericValue]) -> list[StripTarget]:
    raw_targets = [
        StripTarget(
            value=generic_value.original_value,
            placeholder=generic_value.placeholder,
            source_relpath=generic_value.source_relpath,
            field=generic_value.field,
            source_detail=generic_value.location.to_source_detail(generic_value.field),
            occurrence_index=generic_value.location.occurrence_index_identity(),
            location_fmt=generic_value.location.fmt,
            line_number=generic_value.location.line_number,
            json_pointer=generic_value.location.json_pointer,
            toml_section=generic_value.location.toml_section,
        )
        for generic_value in generic_values
    ]
    targets_by_identity: dict[tuple[str, str, str, int, str], StripTarget] = {}
    for target in raw_targets:
        if not target.value or not target.placeholder:
            continue
        identity = (
            target.source_relpath,
            target.field,
            target.source_detail,
            target.occurrence_index,
            target.value,
        )
        targets_by_identity.setdefault(identity, target)
    return sorted(
        targets_by_identity.values(),
        key=lambda target: (-len(target.value), target.source_relpath, target.occurrence_index),
    )


@dataclass(frozen=True)
class LocatedReplacementSummary:
    total_replacements: int
    matched_files: set[Path]


def replace_located_strip_targets(
    targets_by_file: dict[Path, list[StripTarget]],
) -> LocatedReplacementSummary:
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
    if not target.json_pointer:
        return None
    return find_json_string_value_span(text, target.json_pointer, target.value)


def _toml_value_span(text: str, target: StripTarget) -> Optional[tuple[int, int]]:
    if not target.toml_section or not target.field:
        return None
    return find_toml_value_span(
        text,
        section=target.toml_section,
        field=target.field,
        expected_value=target.value,
    )


def _nth_value_span(text: str, value: str, occurrence_index: int) -> Optional[tuple[int, int]]:
    target_occurrence = occurrence_index if occurrence_index > 0 else 1
    start = seen = 0
    while True:
        index = text.find(value, start)
        if index < 0:
            return None
        seen += 1
        if seen == target_occurrence:
            return index, index + len(value)
        start = index + len(value)


@dataclass(frozen=True)
class StripSummary:
    total_replacements: int
    targets_matched: int


def replace_values_in_staging(
    staging_root: Path,
    replacements: list[tuple[str, str]],
    *,
    scan_only_prefix: str = "_scan_only",
) -> StripSummary:
    targets = [
        StripTarget(value=value, placeholder=placeholder)
        for value, placeholder in replacements
        if value
    ]
    if not targets:
        return StripSummary(total_replacements=0, targets_matched=0)

    total = matched = 0
    for file_path in _text_files(staging_root, scan_only_prefix):
        try:
            text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        updated = text
        file_replaced = 0
        for target in targets:
            count = updated.count(target.value)
            if count > 0:
                updated = updated.replace(target.value, target.placeholder)
                file_replaced += count
        if file_replaced > 0:
            file_path.write_text(updated, encoding="utf-8")
            total += file_replaced
            matched += 1
    return StripSummary(total_replacements=total, targets_matched=matched)


def replace_strip_targets_in_staging(
    staging_root: Path,
    targets: list[StripTarget],
    *,
    scan_only_prefix: str = "_scan_only",
) -> StripSummary:
    if not targets:
        return StripSummary(total_replacements=0, targets_matched=0)

    placeholders_by_value: dict[str, set[str]] = defaultdict(set)
    for target in targets:
        if target.value and target.placeholder:
            placeholders_by_value[target.value].add(target.placeholder)

    location_targets: dict[Path, list[StripTarget]] = {}
    global_replacements: list[tuple[str, str]] = []
    for target in targets:
        if not target.value or not target.placeholder:
            continue
        if target.source_relpath and target.occurrence_index > 0:
            file_path = staging_root / target.source_relpath
            location_targets.setdefault(file_path, []).append(target)
        elif len(placeholders_by_value[target.value]) == 1:
            global_replacements.append((target.value, target.placeholder))

    total = 0
    matched_files: set[Path] = set()
    located_summary = replace_located_strip_targets(location_targets)
    total += located_summary.total_replacements
    matched_files.update(located_summary.matched_files)
    if global_replacements:
        summary = replace_values_in_staging(
            staging_root,
            global_replacements,
            scan_only_prefix=scan_only_prefix,
        )
        total += summary.total_replacements
        if summary.targets_matched:
            matched_files.add(staging_root)
    return StripSummary(total_replacements=total, targets_matched=len(matched_files))


def apply_strip(
    staging_root: Path,
    generic_values: Iterable[GenericValue],
    *,
    scan_only_prefix: str = "_scan_only",
) -> StripSummary:
    targets = collect_generic_strip_targets(generic_values)
    if not targets:
        return StripSummary(total_replacements=0, targets_matched=0)
    return replace_strip_targets_in_staging(staging_root, targets, scan_only_prefix=scan_only_prefix)


def _text_files(staging_root: Path, scan_only_prefix: str) -> list[Path]:
    if not staging_root.is_dir():
        return []
    excluded_suffixes = {
        ".zip", ".tar", ".gz", ".bz2", ".xz", ".png", ".jpg", ".jpeg", ".gif", ".ico",
        ".woff", ".woff2", ".ttf", ".eot", ".pyc", ".pyo", ".so", ".dll", ".dylib",
        ".exe", ".bin", ".dat",
    }
    result: list[Path] = []
    for path in staging_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() in excluded_suffixes:
            continue
        try:
            rel = path.relative_to(staging_root).as_posix()
        except ValueError:
            continue
        if not rel.startswith(scan_only_prefix):
            result.append(path)
    return result


def _buyout_entry_strip_specs(entry: dict) -> list[tuple[str, str]]:
    specs: list[tuple[str, str]] = []
    url = entry.get("url")
    if isinstance(url, dict):
        value = str(url.get("value", "")).strip()
        placeholder = str(url.get("placeholder", "")).strip()
        if value:
            specs.append((value, placeholder))
    if specs:
        return specs
    value = str(entry.get("value", "")).strip()
    placeholder = str(entry.get("placeholder", "")).strip()
    if value:
        specs.append((value, placeholder))
    return specs


def _run_strip_by_final_disposition(staging_root: Path, reviewed_scan: dict) -> dict:
    touched_files: set[str] = set()
    items: list[dict] = []
    total_replacements = 0
    for bucket in ("url_proxy", "generic"):
        raw_items = reviewed_scan.get(bucket, [])
        if not isinstance(raw_items, list):
            continue
        for entry in raw_items:
            if not isinstance(entry, dict):
                continue
            disposition = str(entry.get("final_disposition", "")).strip()
            specs = _buyout_entry_strip_specs(entry)
            if disposition not in {REPLACE_WITH_PLACEHOLDER, EXCLUDE_VALUE}:
                raise ValueError(f"unknown disposition: {disposition}")
            placeholder_override = "" if disposition == EXCLUDE_VALUE else None
            item_replacements = 0
            item_files: set[str] = set()
            for value, placeholder in specs:
                result = strip_value_from_staging(
                    staging_root,
                    value,
                    placeholder_override if placeholder_override is not None else placeholder,
                    allow_empty_placeholder=placeholder_override is not None,
                )
                item_files.update(result["replaced_in"])
                item_replacements += result["total_replacements"]
            touched_files.update(item_files)
            total_replacements += item_replacements
            items.append(
                {
                    "bucket": bucket,
                    "disposition": disposition,
                    "replaced_file_count": len(item_files),
                    "total_replacements": item_replacements,
                }
            )
    return {
        "item_count": len(items),
        "touched_file_count": len(touched_files),
        "deleted_file_count": 0,
        "total_replacements": total_replacements,
        "items": items,
    }


def run_strip_batch(staging_root: Path, *, reviewed_scan: dict) -> dict:
    return _run_strip_by_final_disposition(staging_root, reviewed_scan)


__all__ = [
    "LocatedReplacementSummary",
    "StripSummary",
    "StripTarget",
    "apply_strip",
    "collect_generic_strip_targets",
    "replace_located_strip_targets",
    "replace_strip_targets_in_staging",
    "replace_values_in_staging",
    "run_strip_batch",
]
