from __future__ import annotations

from pathlib import Path

from packaging.common.exclusion_rules import looks_like_high_risk_file
from packaging.publish.selection.units import has_skill_owning_path


def is_selected_skill_env_file(target, logical_path: str) -> bool:
    normalized = str(logical_path or "").strip().rstrip("/")
    if target is None or not normalized or not normalized.endswith("/.env"):
        return False
    return has_skill_owning_path(normalized, target=target)


def should_skip_high_risk_stage_file(target, logical_path: str) -> bool:
    normalized = str(logical_path or "").strip().rstrip("/")
    if not normalized:
        return False
    if is_selected_skill_env_file(target, normalized):
        return False
    return looks_like_high_risk_file(normalized) is not None


def validate_staging_high_risk_boundary(target, staging_root: Path) -> None:
    violations = [
        path.relative_to(staging_root).as_posix()
        for path in sorted(staging_root.rglob("*"))
        if path.is_file()
        and should_skip_high_risk_stage_file(
            target,
            path.relative_to(staging_root).as_posix(),
        )
    ]
    if violations:
        raise ValueError("staging contains high-risk files: " + ", ".join(violations))


__all__ = [
    "is_selected_skill_env_file",
    "should_skip_high_risk_stage_file",
    "validate_staging_high_risk_boundary",
]
