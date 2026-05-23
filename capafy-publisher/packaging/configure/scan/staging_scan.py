from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from packaging._shared.contracts.stage_manifest import STAGE_MANIFEST_NAME
from packaging.configure.exclusion import project_scan_excludes
from packaging.runtimes import resolve_target_name

from .file_candidates import collect_api_key_candidates
from .bucket_postprocess import dedupe_scan_results


ScanCollectionResult = Tuple[
    List[dict],
    List[dict],
    Dict[str, str],
    Dict[str, str],
    Dict[str, str],
    Set[str],
]


@dataclass
class ScanCollectionAccumulator:

    candidates: list[dict] = field(default_factory=list)
    excludes: list[dict] = field(default_factory=list)
    env_url_hints: dict[str, str] = field(default_factory=dict)
    service_url_hints: dict[str, str] = field(default_factory=dict)
    value_url_hints: dict[str, str] = field(default_factory=dict)
    referenced_env_names: set[str] = field(default_factory=set)
    _exclude_seen: set[str] = field(default_factory=set, init=False, repr=False)

    def merge(self, result: ScanCollectionResult) -> None:
        (
            candidates,
            file_excludes,
            local_env_hints,
            local_service_hints,
            local_value_hints,
            local_referenced_env_names,
        ) = result
        self.candidates.extend(candidates)
        for item in file_excludes:
            source = str(item.get("source", "") or item.get("path", ""))
            if source and source not in self._exclude_seen:
                self.excludes.append(item)
                self._exclude_seen.add(source)
        for env_name, domain in local_env_hints.items():
            self.env_url_hints.setdefault(env_name, domain)
        for service_name, domain in local_service_hints.items():
            self.service_url_hints.setdefault(service_name, domain)
        for value, domain in local_value_hints.items():
            self.value_url_hints.setdefault(value, domain)
        self.referenced_env_names.update(local_referenced_env_names)


_INTERNAL_SCAN_EXCLUDED_RELPATHS = frozenset({
    STAGE_MANIFEST_NAME,
})


def _is_internal_scan_file(relpath: str) -> bool:
    normalized = str(relpath or "").strip().replace("\\", "/").lstrip("./")
    return normalized in _INTERNAL_SCAN_EXCLUDED_RELPATHS


def _drop_internal_scan_entries(result: dict) -> None:
    for key in ("url_proxy", "generic", "excludes"):
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
) -> tuple[
    list[dict],
    list[dict],
    dict[str, str],
    dict[str, str],
    dict[str, str],
    set[str],
]:
    resolved_target_name = resolve_target_name(target_name)
    staging_path = Path(staging_root)
    is_download = str(platform_agent_type or "").strip() == "download"
    require_referenced_platform_envs = is_download

    accumulator = ScanCollectionAccumulator()
    interesting_process_env_names: set[str] = set()

    accumulator.merge(
        collect_api_key_candidates(
            staging_path,
            "",
            process_env_names=interesting_process_env_names,
            target_name=resolved_target_name,
            require_referenced_platform_envs=require_referenced_platform_envs,
            excluded_relpath_prefixes=("_scan_only",),
        )
    )

    scan_only_root = staging_path / "_scan_only"
    if scan_only_root.is_dir():
        accumulator.merge(
            collect_api_key_candidates(
                scan_only_root,
                "_scan_only",
                process_env_names=interesting_process_env_names,
                target_name=resolved_target_name,
                require_referenced_platform_envs=require_referenced_platform_envs,
                include_stage_excluded_files=True,
            )
        )

    return (
        accumulator.candidates,
        accumulator.excludes,
        accumulator.env_url_hints,
        accumulator.service_url_hints,
        accumulator.value_url_hints,
        accumulator.referenced_env_names,
    )


def _build_scan_groups(
    all_candidates: list[dict],
    env_url_hints: dict[str, str],
    service_url_hints: dict[str, str],
    value_url_hints: dict[str, str],
) -> dict[str, list[dict]]:
    from packaging.configure.url_proxy.group_hints import apply_url_proxy_group_hints
    from packaging.configure.url_proxy.predicates import is_url_proxy_candidate

    apply_url_proxy_group_hints(all_candidates)

    generic_candidates = [c for c in all_candidates if not is_url_proxy_candidate(c)]
    return dedupe_scan_results(
        generic_candidates,
        env_url_hints,
        service_url_hints,
        value_url_hints,
    )


@dataclass(frozen=True)
class StagingScanResult:
    raw_scan: dict[str, Any]
    referenced_env_names: frozenset[str] = frozenset()
    env_url_hints: dict[str, str] = field(default_factory=dict)


def scan_staging_full(
    staging_root: Path,
    *,
    target_name: str,
    platform_agent_type: str = "run_online",
) -> StagingScanResult:
    staging_path = Path(staging_root)
    (
        all_candidates,
        all_excludes,
        env_url_hints,
        service_url_hints,
        value_url_hints,
        referenced_env_names,
    ) = collect_staging_scan_candidates(
        staging_path,
        target_name=target_name,
        platform_agent_type=platform_agent_type,
    )
    scan_groups = _build_scan_groups(
        all_candidates,
        env_url_hints,
        service_url_hints,
        value_url_hints,
    )




    excludes = project_scan_excludes(
        staging_path,
        all_excludes,
    )

    raw_scan: dict[str, Any] = {
        "generic": scan_groups["generic"],
        "excludes": excludes,
    }
    _drop_internal_scan_entries(raw_scan)

    return StagingScanResult(raw_scan=raw_scan, referenced_env_names=frozenset(referenced_env_names), env_url_hints=dict(env_url_hints))


__all__ = [
    "StagingScanResult",
    "collect_staging_scan_candidates",
    "scan_staging_full",
]
