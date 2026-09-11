from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

from packaging.publish.staging.manifest import STAGE_MANIFEST_NAME
from packaging.publish.security.scan.entries import build_generic_from_entry, build_scan_entries
from packaging.runtime import get_target, resolve_target_name

from .file_candidates import collect_api_key_candidates, collect_api_key_candidates_from_file
from .scan_only_paths import normalize_scan_only_relpath


@dataclass(frozen=True)
class ScanOnlySourceFile:
    source_file: Path
    logical_relpath: str


def _normalized_relpath(value: object) -> str:
    normalized = str(value or "").strip().replace("\\", "/").strip("/")
    if not normalized:
        return ""
    return PurePosixPath(normalized).as_posix()


def iter_scan_only_source_files(stage_plan) -> Iterator[ScanOnlySourceFile]:
    seen: set[tuple[Path, str]] = set()
    for source in getattr(stage_plan, "file_sources", []):
        if not getattr(source, "scan_only", False):
            continue
        source_file = Path(getattr(source, "source_file", Path(""))).expanduser()
        logical_relpath = _normalized_relpath(getattr(source, "relative_target_path", ""))
        key = (source_file, logical_relpath)
        if source_file.is_file() and logical_relpath and key not in seen:
            seen.add(key)
            yield ScanOnlySourceFile(source_file=source_file, logical_relpath=logical_relpath)

    for source in getattr(stage_plan, "tree_sources", []):
        if not getattr(source, "scan_only", False):
            continue
        source_root = Path(getattr(source, "source_root", Path(""))).expanduser()
        target_root = _normalized_relpath(getattr(source, "relative_target_root", ""))
        if not source_root.is_dir() or not target_root:
            continue
        for source_file in sorted(path for path in source_root.rglob("*") if path.is_file()):
            try:
                suffix = source_file.relative_to(source_root).as_posix()
            except ValueError:
                continue
            logical_relpath = f"{target_root}/{suffix}" if suffix else target_root
            key = (source_file, logical_relpath)
            if key in seen:
                continue
            seen.add(key)
            yield ScanOnlySourceFile(source_file=source_file, logical_relpath=logical_relpath)


def _is_internal_scan_file(relpath: str) -> bool:
    normalized = str(relpath or "").strip().replace("\\", "/").lstrip("./")
    return normalized == STAGE_MANIFEST_NAME


def collect_staging_scan_candidates(
    staging_root: Path,
    *,
    target_name: str,
    stage_plan=None,
) -> tuple[
    list[dict],
    dict[str, str],
]:
    resolved_target_name = resolve_target_name(target_name)
    staging_path = Path(staging_root)
    candidates, env_url_hints = collect_api_key_candidates(
        staging_path,
        "",
        target_name=resolved_target_name,
        excluded_relpath_prefixes=("_scan_only",),
    )

    target = get_target(resolved_target_name)
    for item in iter_scan_only_source_files(stage_plan):
        logical_relpath = normalize_scan_only_relpath(item.logical_relpath, target=target)
        local_candidates, local_env_hints = collect_api_key_candidates_from_file(
            item.source_file,
            logical_relpath,
            physical_relpath=item.logical_relpath,
        )
        candidates.extend(local_candidates)
        for env_name, domain in local_env_hints.items():
            env_url_hints.setdefault(env_name, domain)

    return candidates, env_url_hints


def _build_generic_entries(
    all_candidates: list[dict],
    env_url_hints: dict[str, str],
) -> list[dict]:
    entries = build_scan_entries(all_candidates, env_url_hints)
    return [
        generic_entry
        for entry in entries
        if (generic_entry := build_generic_from_entry(entry)) is not None
        and not _is_internal_scan_file(
            str(generic_entry.get("source", "") or generic_entry.get("path", ""))
        )
    ]


def scan_staging_full(
    staging_root: Path,
    *,
    target_name: str,
    stage_plan=None,
) -> dict[str, Any]:
    staging_path = Path(staging_root)
    all_candidates, env_url_hints = collect_staging_scan_candidates(
        staging_path,
        target_name=target_name,
        stage_plan=stage_plan,
    )
    return {
        "generic": _build_generic_entries(
            all_candidates,
            env_url_hints,
        ),
    }


__all__ = [
    "ScanOnlySourceFile",
    "collect_staging_scan_candidates",
    "iter_scan_only_source_files",
    "scan_staging_full",
]
