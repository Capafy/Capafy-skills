from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from packaging._shared.contracts.stage_manifest import STAGE_MANIFEST_NAME
from packaging.configure.generic_keys.builder import build_generic_from_entry
from packaging.configure.scan.entries import build_scan_entries
from packaging.runtimes import get_target, resolve_target_name

from .file_candidates import collect_api_key_candidates, collect_api_key_candidates_from_file
from .scan_only_paths import normalize_scan_only_relpath
from .stage_plan_sources import iter_scan_only_source_files


ScanCollectionResult = tuple[
    list[dict],
    dict[str, str],
    dict[str, str],
    dict[str, str],
]


@dataclass
class ScanCollectionAccumulator:

    candidates: list[dict] = field(default_factory=list)
    env_url_hints: dict[str, str] = field(default_factory=dict)
    service_url_hints: dict[str, str] = field(default_factory=dict)
    value_url_hints: dict[str, str] = field(default_factory=dict)

    def merge(self, result: ScanCollectionResult) -> None:
        (
            candidates,
            local_env_hints,
            local_service_hints,
            local_value_hints,
        ) = result
        self.candidates.extend(candidates)
        for env_name, domain in local_env_hints.items():
            self.env_url_hints.setdefault(env_name, domain)
        for service_name, domain in local_service_hints.items():
            self.service_url_hints.setdefault(service_name, domain)
        for value, domain in local_value_hints.items():
            self.value_url_hints.setdefault(value, domain)


def _is_internal_scan_file(relpath: str) -> bool:
    normalized = str(relpath or "").strip().replace("\\", "/").lstrip("./")
    return normalized == STAGE_MANIFEST_NAME


def _drop_internal_scan_entries(result: dict) -> None:
    for key in ("url_proxy", "generic"):
        values = result.get(key)
        if not isinstance(values, list):
            continue
        result[key] = [
            item
            for item in values
            if not (
                isinstance(item, dict)
                and _is_internal_scan_file(str(item.get("source", "") or item.get("path", "")))
            )
        ]


def collect_staging_scan_candidates(
    staging_root: Path,
    *,
    target_name: str,
    platform_agent_type: str = "run_online",
    stage_plan=None,
) -> tuple[
    list[dict],
    dict[str, str],
    dict[str, str],
    dict[str, str],
]:
    resolved_target_name = resolve_target_name(target_name)
    staging_path = Path(staging_root)
    is_download = str(platform_agent_type or "").strip() == "download"
    require_referenced_platform_envs = is_download

    accumulator = ScanCollectionAccumulator()

    accumulator.merge(
        collect_api_key_candidates(
            staging_path,
            "",
            target_name=resolved_target_name,
            require_referenced_platform_envs=require_referenced_platform_envs,
            excluded_relpath_prefixes=("_scan_only",),
        )
    )

    target = get_target(resolved_target_name)
    for item in iter_scan_only_source_files(stage_plan):
        logical_relpath = normalize_scan_only_relpath(item.logical_relpath, target=target)
        accumulator.merge(
            collect_api_key_candidates_from_file(
                item.source_file,
                logical_relpath,
                physical_relpath=item.logical_relpath,
                target_name=resolved_target_name,
                require_referenced_platform_envs=require_referenced_platform_envs,
            )
        )

    return (
        accumulator.candidates,
        accumulator.env_url_hints,
        accumulator.service_url_hints,
        accumulator.value_url_hints,
    )


def _build_generic_entries(
    all_candidates: list[dict],
    env_url_hints: dict[str, str],
    service_url_hints: dict[str, str],
    value_url_hints: dict[str, str],
) -> list[dict]:
    entries = build_scan_entries(all_candidates, env_url_hints, service_url_hints, value_url_hints)
    return [
        generic_entry
        for entry in entries
        if (generic_entry := build_generic_from_entry(entry)) is not None
    ]


def scan_staging_full(
    staging_root: Path,
    *,
    target_name: str,
    platform_agent_type: str = "run_online",
    stage_plan=None,
) -> dict[str, Any]:
    staging_path = Path(staging_root)
    (
        all_candidates,
        env_url_hints,
        service_url_hints,
        value_url_hints,
    ) = collect_staging_scan_candidates(
        staging_path,
        target_name=target_name,
        platform_agent_type=platform_agent_type,
        stage_plan=stage_plan,
    )
    generic_entries = _build_generic_entries(
        all_candidates,
        env_url_hints,
        service_url_hints,
        value_url_hints,
    )

    raw_scan: dict[str, Any] = {
        "generic": generic_entries,
    }
    _drop_internal_scan_entries(raw_scan)

    return raw_scan


__all__ = [
    "collect_staging_scan_candidates",
    "scan_staging_full",
]
