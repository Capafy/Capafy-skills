from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import Iterable, Union

from packaging.common.final_zip_files import final_zip_staging_file_relpaths
from packaging.runtime.contracts import GenericValue, PROCESS_ENV_SOURCE
from packaging.publish.security.sensitive.placeholders import split_source

_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:/")


def normalize_packaged_source_relpath(source: object) -> str:
    raw_source = str(source or "").strip()
    source_relpath, _source_detail = split_source(raw_source)
    normalized = source_relpath.replace("\\", "/").strip()
    if not normalized or normalized == PROCESS_ENV_SOURCE:
        return ""
    if normalized.startswith("/") or _WINDOWS_DRIVE_RE.match(normalized):
        return ""
    pure = PurePosixPath(normalized)
    if any(part == ".." for part in pure.parts):
        return ""
    normalized = pure.as_posix()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.strip("/")
    if normalized in ("", "."):
        return ""
    return normalized


def _staging_path(staging_root: Union[str, Path]) -> Path:
    if isinstance(staging_root, str) and not staging_root.strip():
        raise ValueError("staging_root is required for source boundary checks")
    staging_path = Path(staging_root)
    if not staging_path.is_dir():
        raise ValueError("staging_root is required for source boundary checks")
    return staging_path


def final_zip_source_relpaths(
    *,
    staging_root: Union[str, Path],
) -> frozenset[str]:
    return final_zip_staging_file_relpaths(_staging_path(staging_root))


def deep_scan_file_boundary(
    *,
    staging_root: Union[str, Path],
) -> dict[str, object]:
    staging_path = _staging_path(staging_root)
    final_sources = final_zip_source_relpaths(
        staging_root=staging_path,
    )
    items: list[dict[str, object]] = []
    summary = {
        "total_files": 0,
        "reviewable_files": 0,
        "unreviewable_files": 0,
    }
    for file_path in sorted(path for path in staging_path.rglob("*") if path.is_file()):
        relpath = normalize_packaged_source_relpath(file_path.relative_to(staging_path).as_posix())
        if not relpath:
            continue
        summary["total_files"] += 1
        reason = ""
        reviewable = relpath in final_sources
        if not reviewable:
            reason = "not_in_final_package"
        if reviewable:
            summary["reviewable_files"] += 1
        else:
            summary["unreviewable_files"] += 1
        item: dict[str, object] = {
            "path": relpath,
            "reviewable": reviewable,
        }
        if reason:
            item["reason"] = reason
        items.append(item)
    return {
        "scan_files": items,
        "scan_files_summary": summary,
    }


def filter_generic_payload_items(
    items: Iterable[object],
    *,
    staging_root: Union[str, Path],
) -> list[dict]:
    result: list[dict] = []
    final_sources = final_zip_source_relpaths(
        staging_root=staging_root,
    )
    for item in items:
        if not isinstance(item, dict):
            continue
        source = normalize_packaged_source_relpath(item.get("source"))
        if source not in final_sources:
            continue
        copied = dict(item)
        copied["source"] = source
        result.append(copied)
    return result


def filter_generic_values_for_packaged_sources(
    generic_values: Iterable[GenericValue],
    *,
    staging_root: Union[str, Path],
) -> tuple[GenericValue, ...]:
    result: list[GenericValue] = []
    final_sources = final_zip_source_relpaths(
        staging_root=staging_root,
    )
    for generic_value in generic_values:
        source = normalize_packaged_source_relpath(generic_value.source_relpath)
        if source not in final_sources:
            continue
        result.append(replace(generic_value, source_relpath=source))
    return tuple(result)


__all__ = [
    "deep_scan_file_boundary",
    "filter_generic_payload_items",
    "filter_generic_values_for_packaged_sources",
    "final_zip_source_relpaths",
    "normalize_packaged_source_relpath",
]
