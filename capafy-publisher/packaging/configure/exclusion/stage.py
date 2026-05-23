from __future__ import annotations

from pathlib import Path

from packaging._shared.common.exclusion_rules import exclude_reason_code_for_path, looks_like_high_risk_file
from packaging._shared.contracts.path_shapes import basic_owning_selectable_paths, unit_type_from_path
from packaging._shared.runtimes.contracts import call_optional_target_hook


def is_redacted_runtime_env_file(target, logical_path: str) -> bool:
    normalized = str(logical_path or "").strip().rstrip("/")
    if not normalized:
        return False
    profile = getattr(target, "profile", None)
    if not isinstance(profile, dict):
        return False

    fixed_stage_paths = {
        str(spec.get("target_path", "")).strip().rstrip("/")
        for spec in profile.get("fixed_stage_files", [])
        if isinstance(spec, dict) and str(spec.get("target_path", "")).strip()
    }
    basename = Path(normalized).name
    return normalized in fixed_stage_paths and (basename == ".env" or basename.startswith(".env."))


def is_selected_skill_env_file(target, logical_path: str) -> bool:
    normalized = str(logical_path or "").strip().rstrip("/")
    if target is None or not normalized or not normalized.endswith("/.env"):
        return False

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


def should_skip_high_risk_stage_file(target, logical_path: str) -> bool:
    normalized = str(logical_path or "").strip().rstrip("/")
    if not normalized:
        return False
    if is_redacted_runtime_env_file(target, normalized):
        return False
    if is_selected_skill_env_file(target, normalized):
        return False
    return looks_like_high_risk_file(normalized) is not None


def scan_only_excluded_credential_relpath(target_relpath: str, *, target) -> str | None:
    normalized = str(target_relpath or "").strip().rstrip("/")
    prefix = "_scan_only/"
    if not normalized.startswith(prefix):
        return None
    logical_path = normalized[len(prefix) :]
    if is_redacted_runtime_env_file(target, logical_path):
        return None
    return logical_path if exclude_reason_code_for_path(logical_path) is not None else None


__all__ = [
    "is_redacted_runtime_env_file",
    "is_selected_skill_env_file",
    "scan_only_excluded_credential_relpath",
    "should_skip_high_risk_stage_file",
]
