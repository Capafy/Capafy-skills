from __future__ import annotations
from typing import Optional

import json
from pathlib import Path

from packaging._shared.selection.inventory import build_skill_inventory
from packaging._shared.config_files.toml_loader import tomllib
from packaging._shared.env_profiles.config_files import collect_required_packaged_config_paths
from packaging._shared.runtimes.support import unique_non_empty_strings
from packaging.runtimes.validation_files import (
    collect_present_runtime_paths,
    collect_validation_targets,
    validate_target_file,
)


def _developer_next_steps_from_checks(checks: list[dict]) -> list[str]:
    steps: list[str] = []
    seen: set[str] = set()
    for check in checks:
        if not isinstance(check, dict) or check.get("kind") != "blocking" or check.get("ok"):
            continue
        for step in unique_non_empty_strings(check.get("developer_next_steps")):
            if step in seen:
                continue
            steps.append(step)
            seen.add(step)
    return steps


def _layout_next_steps(env_id: str) -> list[str]:
    return [
        f"Confirm {env_id} staging or bundle includes at least a workspace, config files, or a skill root",
        "Rerun stage / package, then run validate-runtime again",
    ]


def _required_stage_files_next_steps(missing_paths: list[str]) -> list[str]:
    steps = [f"Restore required staged file: {path}" for path in missing_paths]
    steps.append("Rerun stage / package, then run validate-runtime again")
    return steps


def _config_parse_next_steps(failed_targets: list[str]) -> list[str]:
    steps = [f"Fix config file syntax errors: {path}" for path in failed_targets]
    if not steps:
        steps.append("Fix config file syntax errors")
    steps.append("Rerun package and then validate-runtime")
    return steps


def _packaged_skills_next_steps(missing_skill_md: list[dict]) -> list[str]:
    missing_paths = [str(item.get("path", "")).strip() for item in missing_skill_md if str(item.get("path", "")).strip()]
    steps: list[str] = []
    if missing_paths:
        steps.append(f"Add SKILL.md to these directories: {', '.join(missing_paths)}")
    steps.append("If these directories are not required, exclude them from selection_groups and package again")
    steps.append("Rerun package and then validate-runtime")
    return steps


def validate_env_runtime(
    profile: dict,
    runtime_root: Path,
    *,
    env_id: str,
) -> dict:
    checks: list[dict] = []
    errors: list[str] = []
    warnings: list[str] = []

    present_paths = collect_present_runtime_paths(profile, runtime_root)
    required_paths = collect_required_packaged_config_paths(profile)
    missing_required_paths = [
        path for path in required_paths
        if path not in present_paths and not (runtime_root / path).exists()
    ]
    required_files_ok = not missing_required_paths
    if required_paths:
        checks.append(
            {
                "id": f"{env_id}_required_stage_files",
                "kind": "blocking",
                "ok": required_files_ok,
                "summary": (
                    f"{len(required_paths)} required staged files are present"
                    if required_files_ok
                    else "Some required staged files are missing"
                ),
                "required_paths": required_paths,
                **(
                    {}
                    if required_files_ok
                    else {
                        "missing_required_paths": missing_required_paths,
                        "developer_next_steps": _required_stage_files_next_steps(missing_required_paths),
                    }
                ),
            }
        )
        if not required_files_ok:
            errors.append(
                f"{env_id} runtime copy is missing required staged files: {', '.join(missing_required_paths)}"
            )
            developer_next_steps = _developer_next_steps_from_checks(checks)
            return {
                "ok": False,
                "checks": checks,
                "errors": errors,
                "warnings": warnings,
                "developer_next_steps": developer_next_steps,
            }

    layout_ok = bool(present_paths)
    checks.append(
        {
            "id": f"{env_id}_runtime_layout",
            "kind": "blocking",
            "ok": layout_ok,
            "summary": "Found runtime-critical paths" if layout_ok else "Runtime-critical paths were not found",
            "present_paths": present_paths,
            **({} if layout_ok else {"developer_next_steps": _layout_next_steps(env_id)}),
        }
    )
    if not layout_ok:
        errors.append(f"{env_id} runtime copy does not contain config files, a workspace, or a skill root")
        developer_next_steps = _developer_next_steps_from_checks(checks)
        return {
            "ok": False,
            "checks": checks,
            "errors": errors,
            "warnings": warnings,
            "developer_next_steps": developer_next_steps,
        }

    config_targets = collect_validation_targets(profile, runtime_root)
    config_ok = True
    config_results: list[str] = []
    config_errors: list[str] = []
    failed_config_targets: list[str] = []
    for target in config_targets:
        try:
            _, summary = validate_target_file(runtime_root, target)
        except (OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
            config_ok = False
            error_text = str(exc)
            config_results.append(error_text)
            config_errors.append(error_text)
            failed_config_targets.append(target["path"])
        else:
            config_results.append(summary)
    checks.append(
        {
            "id": f"{env_id}_config_parse",
            "kind": "blocking",
            "ok": config_ok,
            "summary": (
                f"{len(config_targets)} config files parsed successfully"
                if config_ok
                else "Some config files failed to parse"
            ),
            "details": config_results,
            **(
                {}
                if config_ok
                else {"developer_next_steps": _config_parse_next_steps(failed_config_targets)}
            ),
        }
    )
    if not config_ok:
        errors.extend(config_errors)

    included_skills, suspicious_skills = build_skill_inventory(runtime_root)
    missing_skill_md = []
    for item in suspicious_skills:
        reasons = [
            str(reason).strip().lower()
            for reason in item.get("reasons", [])
            if str(reason).strip()
        ]
        if "missing skill.md" in reasons:
            missing_skill_md.append(item)
    skills_ok = not missing_skill_md
    checks.append(
        {
            "id": f"{env_id}_packaged_skills",
            "kind": "blocking",
            "ok": skills_ok,
            "summary": (
                f"{len(included_skills)} packaged skills have valid structure"
                if skills_ok
                else "Some packaged skills are missing SKILL.md"
            ),
            "packaged_skill_count": len(included_skills),
            "missing_skill_md": [item["path"] for item in missing_skill_md],
            **(
                {}
                if skills_ok
                else {"developer_next_steps": _packaged_skills_next_steps(missing_skill_md)}
            ),
        }
    )
    if not skills_ok:
        errors.append(f"{env_id} packaged skills contain directories missing SKILL.md")

    non_blocking_suspicious = [
        item
        for item in suspicious_skills
        if item not in missing_skill_md
    ]
    if non_blocking_suspicious:
        warnings.append(
            f"{env_id} packaged content has {len(non_blocking_suspicious)} suspicious skill(s) in total; review their structure or size manually"
        )

    developer_next_steps = _developer_next_steps_from_checks(checks)

    return {
        "ok": not errors,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "developer_next_steps": developer_next_steps,
    }


__all__ = ["validate_env_runtime"]
