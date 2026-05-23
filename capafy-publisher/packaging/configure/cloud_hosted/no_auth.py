from __future__ import annotations

from pathlib import PurePosixPath

from packaging._shared.common.exclusion_rules import exclude_reason_code_for_path
from packaging._shared.common.packaged_files import is_credential_excluded_dir
from packaging._shared.runtimes.contracts import call_optional_target_hook


_OPENCLAW_WORKSPACE_SOURCE_KEY = ".openclaw/workspace"


def selected_workflow_unit_paths(
    *,
    selected_skill_paths: set[str] | None,
    selected_plugin_paths: set[str] | None,
    selected_cron_paths: set[str] | None,
) -> set[str]:
    return {
        str(path).strip().rstrip("/")
        for group in (selected_skill_paths or set(), selected_plugin_paths or set(), selected_cron_paths or set())
        for path in group
        if str(path).strip()
    }


def _workflow_runtime_auth_paths(*, bundle_context: dict, stage_plan) -> set[str]:
    env_id = str(bundle_context.get("env_id") or stage_plan.metadata.get("env_id") or "").strip().lower()
    if env_id != "openclaw":
        return set()
    runtime_paths: set[str] = set()
    for tree_source in getattr(stage_plan, "tree_sources", []):
        source_key = str(getattr(tree_source, "source_key", "")).strip()
        display_prefix = str(getattr(tree_source, "display_prefix", "")).strip().rstrip("/")
        if source_key != _OPENCLAW_WORKSPACE_SOURCE_KEY or not display_prefix:
            continue
        runtime_paths.add(f"{display_prefix}/auth-profiles.json")
    return runtime_paths


def _is_workflow_related_credential_skip(
    skipped_path: str,
    *,
    selected_unit_paths: set[str] | None,
    runtime_auth_paths: set[str],
    target,
) -> bool:
    normalized = skipped_path.rstrip("/")
    if not normalized:
        return False
    if normalized in runtime_auth_paths:
        return True
    if not selected_unit_paths:
        return False
    if normalized in selected_unit_paths:
        return True
    if any(normalized.startswith(f"{selected_path}/") for selected_path in selected_unit_paths):
        return True
    owning_paths = tuple(
        str(path).strip().rstrip("/")
        for path in call_optional_target_hook(
            target,
            "owning_selectable_paths",
            normalized,
            default=(),
        )
    )
    return any(path in selected_unit_paths for path in owning_paths)


def build_workflow_related_no_auth_paths(
    skipped: list[str],
    *,
    selected_skill_paths: set[str] | None,
    selected_plugin_paths: set[str] | None,
    selected_cron_paths: set[str] | None,
    bundle_context: dict,
    stage_plan,
    target,
) -> list[str]:
    selected_unit_paths: set[str] | None = None
    if any(group is not None for group in (selected_skill_paths, selected_plugin_paths, selected_cron_paths)):
        selected_unit_paths = selected_workflow_unit_paths(
            selected_skill_paths=selected_skill_paths,
            selected_plugin_paths=selected_plugin_paths,
            selected_cron_paths=selected_cron_paths,
        )
    runtime_auth_paths = _workflow_runtime_auth_paths(
        bundle_context=bundle_context,
        stage_plan=stage_plan,
    )
    return sorted({
        path.rstrip("/")
        for path in skipped
        if (
            (
                not path.endswith("/")
                and exclude_reason_code_for_path(path) is not None
            ) or (
                path.endswith("/")
                and is_credential_excluded_dir(PurePosixPath(path.rstrip("/")).name)
            )
        ) and _is_workflow_related_credential_skip(
            path,
            selected_unit_paths=selected_unit_paths,
            runtime_auth_paths=runtime_auth_paths,
            target=target,
        )
    })


__all__ = [
    "build_workflow_related_no_auth_paths",
    "selected_workflow_unit_paths",
]
