from __future__ import annotations

import json
from pathlib import Path

from packaging.configure.selection.inventory import build_skill_inventory
from packaging._shared.common.constants import ENV_REF_PATTERN
from packaging._shared.common.toml_loader import tomllib
from packaging._shared.runtimes.support import unique_non_empty_strings
from .env_runtime_files import (
    collect_present_runtime_paths,
    collect_required_runtime_paths,
    collect_validation_targets,
    validate_target_file,
)


def _normalize_version(raw_value: object) -> str:
    import re

    semver_pattern = re.compile(r"(?:\d+\.)+\d+")
    if raw_value is None:
        return ""
    text = str(raw_value).strip()
    if not text:
        return ""
    match = semver_pattern.search(text)
    if match:
        return match.group(0)
    return text


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


def _runtime_manifest_next_steps(env_id: str, summary: str) -> list[str]:
    if "parse failed" in summary:
        return [
            "Fix the JSON syntax error in agent.runtime_environment.json",
            "Rerun stage / package, then run validate-runtime again",
        ]
    return [
        f"Confirm {env_id} package includes agent.runtime_environment.json",
        "Rerun stage / package, then run validate-runtime again",
    ]


def _version_snapshot_next_steps(normalized_expected: str) -> list[str]:
    return [
        f"Rerun validate-runtime in an environment whose version snapshot matches {normalized_expected}",
        "If the target runtime version changed, update the host's recorded target version before retrying",
    ]


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
    expected_version: str | None = None,
) -> dict:
    checks: list[dict] = []
    errors: list[str] = []
    warnings: list[str] = []

    present_paths = collect_present_runtime_paths(profile, runtime_root)
    required_paths = collect_required_runtime_paths(profile)
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
                "target": env_id,
                "supported": True,
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
            "target": env_id,
            "supported": True,
            "ok": False,
            "checks": checks,
            "errors": errors,
            "warnings": warnings,
            "developer_next_steps": developer_next_steps,
        }

    runtime_manifest_path = runtime_root / "agent.runtime_environment.json"
    runtime_manifest: dict[str, object] | None = None
    manifest_ok = runtime_manifest_path.is_file()
    manifest_summary = "missing agent.runtime_environment.json"
    version_field = ""
    version_value = None
    if manifest_ok:
        try:
            loaded = json.loads(runtime_manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            manifest_ok = False
            manifest_summary = f"agent.runtime_environment.json parse failed: {exc}"
        else:
            if isinstance(loaded, dict):
                runtime_manifest = loaded
                runtime_env = profile.get("runtime_env", {})
                if isinstance(runtime_env, dict):
                    version_field = str(runtime_env.get("field", "")).strip()
                if version_field:
                    version_value = loaded.get(version_field)
                    manifest_summary = f"agent.runtime_environment.json parsed successfully; {version_field}={version_value or 'unknown'}"
                else:
                    manifest_summary = "agent.runtime_environment.json parsed successfully"
            else:
                manifest_ok = False
                manifest_summary = "agent.runtime_environment.json top-level value must be an object"
    checks.append(
        {
            "id": f"{env_id}_runtime_environment_manifest",
            "kind": "blocking",
            "ok": manifest_ok,
            "summary": manifest_summary,
            **(
                {}
                if manifest_ok
                else {"developer_next_steps": _runtime_manifest_next_steps(env_id, manifest_summary)}
            ),
        }
    )
    if not manifest_ok:
        errors.append(manifest_summary)
        developer_next_steps = _developer_next_steps_from_checks(checks)
        return {
            "target": env_id,
            "supported": True,
            "ok": False,
            "checks": checks,
            "errors": errors,
            "warnings": warnings,
            "developer_next_steps": developer_next_steps,
        }

    normalized_expected = _normalize_version(expected_version)
    normalized_actual = _normalize_version(version_value)
    if normalized_expected:
        version_matches = bool(normalized_actual) and normalized_actual == normalized_expected
        checks.append(
            {
                "id": f"{env_id}_runtime_version_snapshot",
                "kind": "blocking",
                "ok": version_matches,
                "summary": (
                    f"runtime snapshot version matches {normalized_expected}"
                    if version_matches
                    else f"runtime snapshot version is {normalized_actual or 'unknown'}, expected {normalized_expected} does not match"
                ),
                "actual_version": normalized_actual,
                "expected_version": normalized_expected,
                **(
                    {}
                    if version_matches
                    else {"developer_next_steps": _version_snapshot_next_steps(normalized_expected)}
                ),
            }
        )
        if not version_matches:
            errors.append(
                f"{env_id} runtime snapshot version is {normalized_actual or 'unknown'}, expected {normalized_expected} does not match"
            )

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


    missing_env_vars: list[dict] = []
    for skill_item in included_skills:
        skill_path_str = str(skill_item.get("path", ""))
        skill_dir = runtime_root / skill_path_str
        scripts_dir = skill_dir / "scripts"
        if not scripts_dir.is_dir():
            continue
        for script_file in sorted(scripts_dir.rglob("*.py")):
            try:
                script_text = script_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for match in ENV_REF_PATTERN.finditer(script_text):
                env_name = next((g for g in match.groups() if g), None)
                if not env_name:
                    continue
                if any(d["env_name"] == env_name and d["skill_path"] == skill_path_str for d in missing_env_vars):
                    continue
                missing_env_vars.append({
                    "env_name": env_name,
                    "skill_path": skill_path_str,
                    "script": str(script_file.relative_to(runtime_root)),
                })
    if missing_env_vars:
        unique_env_names = sorted({d["env_name"] for d in missing_env_vars})
        env_dep_summary = f"skill scripts reference {len(unique_env_names)} environment variables: {', '.join(unique_env_names[:5])}"
        if len(unique_env_names) > 5:
            env_dep_summary += f" and {len(unique_env_names)} total"
        checks.append({
            "id": f"{env_id}_skill_env_dependencies",
            "kind": "advisory",
            "ok": True,
            "summary": env_dep_summary,
            "env_var_references": missing_env_vars[:20],
        })
        warnings.append(f"{env_dep_summary}; confirm these environment variables are available at runtime (platform-managed or user-provided)")

    non_blocking_suspicious = [
        item
        for item in suspicious_skills
        if item not in missing_skill_md
    ]
    if non_blocking_suspicious:
        warnings.append(
            f"{env_id} packaged content has {len(non_blocking_suspicious)} suspicious skill(s) in total; review their structure or size manually"
        )

    if runtime_manifest is not None and version_field and version_field not in runtime_manifest:
        warnings.append(f"agent.runtime_environment.json is missing field {version_field}")

    developer_next_steps = _developer_next_steps_from_checks(checks)

    return {
        "target": env_id,
        "supported": True,
        "ok": not errors,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "developer_next_steps": developer_next_steps,
    }


__all__ = ["validate_env_runtime"]
