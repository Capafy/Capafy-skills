from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import Iterable, Union

from packaging._shared.common.final_zip_files import final_zip_staging_file_relpaths
from packaging._shared.contracts.bundle_context import BUNDLE_CONTEXT_NAME, VALID_AGENT_TYPES
from packaging._shared.contracts.stage_manifest import STAGE_MANIFEST_NAME, load_stage_manifest
from packaging.configure.contracts import GenericValue, PROCESS_ENV_SOURCE
from packaging.configure.sensitive.placeholders import split_source

_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:/")
_DEFAULT_SCAN_ONLY_PREFIXES = ("_scan_only",)


def _normalize_agent_type(agent_type: object) -> str:
    normalized = str(agent_type or "").strip()
    if normalized not in VALID_AGENT_TYPES:
        raise ValueError("agent_type must be one of: run_online, download")
    return normalized


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


def _scan_only_prefixes(staging_root: Path) -> tuple[str, ...]:
    prefixes: list[str] = list(_DEFAULT_SCAN_ONLY_PREFIXES)
    try:
        manifest = load_stage_manifest(staging_root)
    except ValueError:
        manifest = {}
    manifest_prefixes = manifest.get("scan_only_prefixes", [])
    if isinstance(manifest_prefixes, list):
        prefixes.extend(str(item or "").strip() for item in manifest_prefixes)
    return tuple(
        dict.fromkeys(
            prefix
            for prefix in (normalize_packaged_source_relpath(item) for item in prefixes)
            if prefix
        )
    )


def _final_zip_exclude_prefixes(staging_root: Path, *, agent_type: str) -> tuple[str, ...]:
    if agent_type == "download":
        return _scan_only_prefixes(staging_root)
    return _DEFAULT_SCAN_ONLY_PREFIXES


def _final_zip_exclude_paths(excluded_relpaths: Iterable[object], *, agent_type: str) -> set[str]:
    excluded = {
        normalized
        for normalized in (normalize_packaged_source_relpath(item) for item in excluded_relpaths)
        if normalized
    }
    excluded.add(STAGE_MANIFEST_NAME)
    if agent_type == "download":
        excluded.add(BUNDLE_CONTEXT_NAME)
    return excluded


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
    excluded_relpaths: Iterable[object],
    agent_type: str,
) -> frozenset[str]:
    resolved_agent_type = _normalize_agent_type(agent_type)
    staging_path = _staging_path(staging_root)
    return final_zip_staging_file_relpaths(
        staging_path,
        exclude_paths=_final_zip_exclude_paths(excluded_relpaths, agent_type=resolved_agent_type),
        exclude_prefixes=_final_zip_exclude_prefixes(staging_path, agent_type=resolved_agent_type),
    )


def is_packaged_source_path(
    source: object,
    *,
    staging_root: Union[str, Path],
    excluded_relpaths: Iterable[object] = (),
    agent_type: str,
) -> bool:
    normalized = normalize_packaged_source_relpath(source)
    if not normalized or normalized == STAGE_MANIFEST_NAME:
        return False
    return normalized in final_zip_source_relpaths(
        staging_root=staging_root,
        excluded_relpaths=tuple(excluded_relpaths),
        agent_type=agent_type,
    )


def filter_generic_payload_items(
    items: Iterable[object],
    *,
    staging_root: Union[str, Path],
    excluded_relpaths: Iterable[object] = (),
    agent_type: str,
) -> list[dict]:
    result: list[dict] = []
    final_sources = final_zip_source_relpaths(
        staging_root=staging_root,
        excluded_relpaths=tuple(excluded_relpaths),
        agent_type=agent_type,
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
    excluded_relpaths: Iterable[object] = (),
    agent_type: str,
) -> tuple[GenericValue, ...]:
    result: list[GenericValue] = []
    final_sources = final_zip_source_relpaths(
        staging_root=staging_root,
        excluded_relpaths=tuple(excluded_relpaths),
        agent_type=agent_type,
    )
    for generic_value in generic_values:
        source = normalize_packaged_source_relpath(generic_value.source_relpath)
        if source not in final_sources:
            continue
        result.append(replace(generic_value, source_relpath=source))
    return tuple(result)


__all__ = [
    "filter_generic_payload_items",
    "filter_generic_values_for_packaged_sources",
    "final_zip_source_relpaths",
    "is_packaged_source_path",
    "normalize_packaged_source_relpath",
]
