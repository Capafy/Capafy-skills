from __future__ import annotations
from typing import Optional

from pathlib import Path

from packaging._shared.common.exclusion_rules import exclude_reason_code_for_path, looks_like_high_risk_file
from packaging.configure.selection.unit_types import has_skill_owning_path


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

    return has_skill_owning_path(normalized, target=target)


def should_skip_high_risk_stage_file(target, logical_path: str) -> bool:
    normalized = str(logical_path or "").strip().rstrip("/")
    if not normalized:
        return False
    if is_redacted_runtime_env_file(target, normalized):
        return False
    if is_selected_skill_env_file(target, normalized):
        return False
    return looks_like_high_risk_file(normalized) is not None


def scan_only_excluded_credential_relpath(target_relpath: str, *, target) -> Optional[str]:
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
