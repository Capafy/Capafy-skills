from __future__ import annotations

from pathlib import Path, PurePosixPath

from packaging._shared.common.fs import (
    display_stage_path,
    read_text,
    relpath as fs_relpath,
)
from packaging._shared.common.packaged_files import iter_packaged_files
from packaging._shared.policies.content_scan import should_skip_content_scan_for_file
from packaging.configure.exclusion import build_exclude_entry, looks_like_high_risk_file
from packaging.configure.generic_keys import collect_generic_key_candidates
from packaging._shared.contracts.path_shapes import basic_owning_selectable_paths, unit_type_from_path
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


def _is_runtime_required_env_file(relpath: str, *, target_name: str | None = None) -> bool:
    if not relpath:
        return False
    target = get_target(target_name) if target_name else get_default_target()
    profile = getattr(target, "profile", None)
    if not isinstance(profile, dict):
        return False

    normalized = relpath.strip().rstrip("/")
    fixed_stage_files = profile.get("fixed_stage_files", [])
    if not isinstance(fixed_stage_files, list):
        return False

    fixed_stage_paths = {
        str(spec.get("target_path", "")).strip().rstrip("/")
        for spec in fixed_stage_files
        if isinstance(spec, dict) and str(spec.get("target_path", "")).strip()
    }
    basename = PurePosixPath(normalized).name
    return normalized in fixed_stage_paths and (basename == ".env" or basename.startswith(".env."))


def _is_selected_skill_env_file(relpath: str, *, target_name: str | None = None) -> bool:
    normalized = str(relpath or "").strip().rstrip("/")
    if not normalized or not normalized.endswith("/.env"):
        return False

    target = get_target(target_name) if target_name else get_default_target()
    owning_paths = tuple(
        str(path).strip().rstrip("/")
        for path in call_optional_target_hook(
            target,
            "owning_selectable_paths",
            normalized,
            default=basic_owning_selectable_paths(normalized),
        )
    )
    return any(
        path
        and str(
            call_optional_target_hook(
                target,
                "infer_unit_type_from_path",
                path,
                default=unit_type_from_path(path),
            )
        ).strip()
        == "skill"
        for path in owning_paths
    )


def collect_api_key_candidates_from_file(
    path: Path,
    relpath: str,
    physical_relpath: str | None = None,
    process_env_names: set[str] | None = None,
    target_name: str | None = None,
    require_referenced_platform_envs: bool = False,
) -> tuple[list[dict], list[dict], dict[str, str], dict[str, str], dict[str, str], set[str]]:
    target = get_target(target_name) if target_name else get_default_target()
    active_target_name = target_name or getattr(target, "env_id", None)
    candidates: list[dict] = []
    file_excludes: list[dict] = []
    env_url_hints: dict[str, str] = {}
    service_url_hints: dict[str, str] = {}
    value_url_hints: dict[str, str] = {}
    referenced_env_names: set[str] = set()
    is_runtime_required_file = _is_runtime_required_env_file(relpath, target_name=target_name)

    if not path.is_file():
        return (
            candidates,
            file_excludes,
            env_url_hints,
            service_url_hints,
            value_url_hints,
            referenced_env_names,
        )

    scan_only_source = is_scan_only_source_path(physical_relpath or relpath)
    high_risk_reason = looks_like_high_risk_file(relpath)
    if high_risk_reason and (
        is_runtime_required_file
        or _is_selected_skill_env_file(relpath, target_name=target_name)
    ):
        high_risk_reason = None
    if high_risk_reason:
        exclude_entry = build_exclude_entry(relpath, reason=high_risk_reason, added_by="scan")
        if exclude_entry is not None:
            file_excludes.append(exclude_entry)

    if should_skip_content_scan_for_file(relpath):
        return (
            candidates,
            file_excludes,
            env_url_hints,
            service_url_hints,
            value_url_hints,
            referenced_env_names,
        )

    text, _ = read_text(path)
    if text is None:
        return (
            candidates,
            file_excludes,
            env_url_hints,
            service_url_hints,
            value_url_hints,
            referenced_env_names,
        )

    for env_name, domain in collect_env_url_hints(text).items():
        env_url_hints.setdefault(env_name, domain)
    file_referenced_env_names, file_env_name_hints = collect_referenced_env_names(text, process_env_names)
    referenced_env_names.update(file_referenced_env_names)
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
            file_excludes,
            env_url_hints,
            service_url_hints,
            value_url_hints,
            referenced_env_names,
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
        file_excludes,
        env_url_hints,
        service_url_hints,
        value_url_hints,
        referenced_env_names,
    )


def collect_api_key_candidates(
    root: Path,
    display_prefix: str = "",
    *,
    process_env_names: set[str] | None = None,
    target_name: str | None = None,
    require_referenced_platform_envs: bool = False,
    include_stage_excluded_files: bool = False,
    excluded_relpath_prefixes: tuple[str, ...] = (),
) -> tuple[list[dict], list[dict], dict[str, str], dict[str, str], dict[str, str], set[str]]:
    target = get_target(target_name) if target_name else get_default_target()
    candidates: list[dict] = []
    file_excludes: list[dict] = []
    env_url_hints: dict[str, str] = {}
    service_url_hints: dict[str, str] = {}
    value_url_hints: dict[str, str] = {}
    referenced_env_names: set[str] = set()

    for path in iter_packaged_files(
        root,
        excluded_relpath_prefixes=excluded_relpath_prefixes,
        include_stage_excluded_files=include_stage_excluded_files,
    ):
        physical_relpath = display_stage_path(display_prefix, fs_relpath(path, root))
        relpath = normalize_scan_only_relpath(physical_relpath, target=target)
        (
            file_candidates,
            file_excludes_for_path,
            file_env_hints,
            file_service_hints,
            file_value_hints,
            file_referenced_env_names,
        ) = collect_api_key_candidates_from_file(
            path,
            relpath,
            physical_relpath=physical_relpath,
            process_env_names=process_env_names,
            target_name=target_name,
            require_referenced_platform_envs=require_referenced_platform_envs,
        )
        candidates.extend(file_candidates)
        file_excludes.extend(file_excludes_for_path)
        referenced_env_names.update(file_referenced_env_names)
        for env_name, domain in file_env_hints.items():
            env_url_hints.setdefault(env_name, domain)
        for service_name, domain in file_service_hints.items():
            service_url_hints.setdefault(service_name, domain)
        for value, domain in file_value_hints.items():
            value_url_hints.setdefault(value, domain)

    return (
        candidates,
        file_excludes,
        env_url_hints,
        service_url_hints,
        value_url_hints,
        referenced_env_names,
    )
