from __future__ import annotations
from typing import Optional

from pathlib import Path

from packaging._shared.common.fs import (
    display_stage_path,
    read_text,
    relpath as fs_relpath,
)
from packaging._shared.common.packaged_files import iter_packaged_files
from packaging._shared.policies.content_scan import should_skip_content_scan_for_file
from packaging.configure.generic_keys import collect_generic_key_candidates
from packaging.runtimes import get_default_target, get_target
from packaging._shared.runtimes.contracts import call_optional_target_hook

from .candidate_annotation import annotate_candidate
from .env_reference_scan import collect_env_url_hints, collect_referenced_env_names
from .structured_value_candidates import collect_structured_value_candidates
from .platform_contracts import (
    collect_platform_env_url_hints,
    is_platform_contract_file,
)
from .scan_only_paths import is_scan_only_source_path, normalize_scan_only_relpath
from .special_files import collect_special_file_candidates


def collect_api_key_candidates_from_file(
    path: Path,
    relpath: str,
    physical_relpath: Optional[str] = None,
    target_name: Optional[str] = None,
    require_referenced_platform_envs: bool = False,
) -> tuple[list[dict], dict[str, str], dict[str, str], dict[str, str]]:
    target = get_target(target_name) if target_name else get_default_target()
    active_target_name = target_name or getattr(target, "env_id", None)
    candidates: list[dict] = []
    env_url_hints: dict[str, str] = {}
    service_url_hints: dict[str, str] = {}
    value_url_hints: dict[str, str] = {}
    if not path.is_file():
        return (
            candidates,
            env_url_hints,
            service_url_hints,
            value_url_hints,
        )

    scan_only_source = is_scan_only_source_path(physical_relpath or relpath)
    if should_skip_content_scan_for_file(relpath):
        return (
            candidates,
            env_url_hints,
            service_url_hints,
            value_url_hints,
        )

    text, _ = read_text(path)
    if text is None:
        return (
            candidates,
            env_url_hints,
            service_url_hints,
            value_url_hints,
        )

    for env_name, domain in collect_env_url_hints(text).items():
        env_url_hints.setdefault(env_name, domain)
    file_referenced_env_names, file_env_name_hints = collect_referenced_env_names(text)
    for env_name, domain in file_env_name_hints.items():
        env_url_hints.setdefault(env_name, domain)
    for env_name, domain in collect_platform_env_url_hints(
        target_name=active_target_name,
        referenced_env_names=file_referenced_env_names,
        require_referenced_env_names=require_referenced_platform_envs,
    ).items():
        env_url_hints.setdefault(env_name, domain)

    if is_platform_contract_file(relpath, target_name=active_target_name):
        file_env_hints, file_service_hints, file_value_hints, explicit_candidates = call_optional_target_hook(
            target,
            "collect_special_scan_candidates",
            Path(relpath),
            text,
            annotate_candidate,
            default=({}, {}, {}, []),
        )
        for env_name, domain in file_env_hints.items():
            env_url_hints.setdefault(env_name, domain)
        for service_name, domain in file_service_hints.items():
            service_url_hints.setdefault(service_name, domain)
        for value, domain in file_value_hints.items():
            value_url_hints.setdefault(value, domain)
        candidates.extend(explicit_candidates)

    if scan_only_source:
        return (
            candidates,
            env_url_hints,
            service_url_hints,
            value_url_hints,
        )

    candidates.extend(collect_special_file_candidates(text, relpath))
    structured_scan_enabled = call_optional_target_hook(
        target,
        "should_scan_structured_values",
        relpath,
        default=True,
    )
    candidates.extend(
        collect_structured_value_candidates(
            text,
            relpath,
            enabled=structured_scan_enabled,
        )
    )
    if structured_scan_enabled:
        candidates.extend(collect_generic_key_candidates(text, relpath))

    return (
        candidates,
        env_url_hints,
        service_url_hints,
        value_url_hints,
    )


def collect_api_key_candidates(
    root: Path,
    display_prefix: str = "",
    *,
    target_name: Optional[str] = None,
    require_referenced_platform_envs: bool = False,
    excluded_relpath_prefixes: tuple[str, ...] = (),
) -> tuple[list[dict], dict[str, str], dict[str, str], dict[str, str]]:
    target = get_target(target_name) if target_name else get_default_target()
    candidates: list[dict] = []
    env_url_hints: dict[str, str] = {}
    service_url_hints: dict[str, str] = {}
    value_url_hints: dict[str, str] = {}

    for path in iter_packaged_files(
        root,
        excluded_relpath_prefixes=excluded_relpath_prefixes,
    ):
        physical_relpath = display_stage_path(display_prefix, fs_relpath(path, root))
        relpath = normalize_scan_only_relpath(physical_relpath, target=target)
        (
            file_candidates,
            file_env_hints,
            file_service_hints,
            file_value_hints,
        ) = collect_api_key_candidates_from_file(
            path,
            relpath,
            physical_relpath=physical_relpath,
            target_name=target_name,
            require_referenced_platform_envs=require_referenced_platform_envs,
        )
        candidates.extend(file_candidates)
        for env_name, domain in file_env_hints.items():
            env_url_hints.setdefault(env_name, domain)
        for service_name, domain in file_service_hints.items():
            service_url_hints.setdefault(service_name, domain)
        for value, domain in file_value_hints.items():
            value_url_hints.setdefault(value, domain)

    return (
        candidates,
        env_url_hints,
        service_url_hints,
        value_url_hints,
    )
