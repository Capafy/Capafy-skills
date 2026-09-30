from __future__ import annotations

from pathlib import Path
from typing import Any

from packaging.publish.security.scan.entries import build_generic_from_entry, build_scan_entries

from .file_candidates import collect_api_key_candidates, collect_api_key_candidates_from_file
from .scan_only_paths import ScanOnlySourceFile, iter_scan_only_source_files


def collect_staging_scan_candidates(
    staging_root: Path,
    *,
    stage_plan=None,
) -> tuple[
    list[dict],
    dict[str, str],
]:
    staging_path = Path(staging_root)
    candidates, env_url_hints = collect_api_key_candidates(staging_path)

    for item in iter_scan_only_source_files(stage_plan):
        local_candidates, local_env_hints = collect_api_key_candidates_from_file(
            item.source_file,
            item.logical_relpath,
            scan_only_source=True,
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
    ]


def scan_staging_full(
    staging_root: Path,
    *,
    stage_plan=None,
) -> dict[str, Any]:
    staging_path = Path(staging_root)
    all_candidates, env_url_hints = collect_staging_scan_candidates(
        staging_path,
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
