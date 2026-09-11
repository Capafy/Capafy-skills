from __future__ import annotations
from pathlib import Path

from packaging.publish.selection.inventory import build_skill_inventory
from packaging.runtime.support import unique_non_empty_strings


def _collect_present_runtime_paths(profile: dict, runtime_root: Path) -> list[str]:
    present: list[str] = []
    skill_roots = profile.get("skill_roots", [])
    if isinstance(skill_roots, list):
        for spec in skill_roots:
            if not isinstance(spec, dict):
                continue
            target_path = str(spec.get("target_path", "")).strip()
            if (
                target_path
                and target_path not in present
                and (runtime_root / target_path).exists()
            ):
                present.append(target_path)

    if (runtime_root / ".agents" / "skills").exists() and ".agents/skills" not in present:
        present.append(".agents/skills")
    return present


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
        f"Confirm {env_id} staging or bundle includes at least a workspace or a skill root",
        "Rerun stage / package, then run validate-runtime again",
    ]


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

    included_skills, suspicious_skills = build_skill_inventory(runtime_root)
    present_paths = _collect_present_runtime_paths(profile, runtime_root)
    for item in included_skills:
        skill_path = str(item.get("path", "")).strip()
        if skill_path and skill_path not in present_paths:
            present_paths.append(skill_path)
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
        errors.append(f"{env_id} runtime copy does not contain a workspace or a skill root")
        developer_next_steps = _developer_next_steps_from_checks(checks)
        return {
            "ok": False,
            "checks": checks,
            "errors": errors,
            "warnings": warnings,
            "developer_next_steps": developer_next_steps,
        }

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
