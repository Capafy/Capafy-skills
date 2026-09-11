from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from packaging.publish.artifacts.bundle_context import validate_agent_type
from packaging.publish.domain.contexts import StageContext
from packaging.publish.profiles.mode_dispatch import get_publish_profile
from packaging.publish.selection.confirmed_workspace_documents import (
    build_confirmed_workspace_document_stage_additions,
)
from packaging.publish.selection.external_skill_bindings import augment_stage_plan_with_selected_external_skill_bindings
from packaging.publish.selection.selection_groups import is_selected_selection_group_item
from packaging.publish.staging.selection_payload import (
    has_explicit_selection_groups,
    load_skills_plan_payload,
    normalize_skills_plan_payload_for_target,
    selection_groups_from_payload,
)
from packaging.publish.selection.symlinks import augment_stage_plan_with_selected_symlinks
from packaging.runtime.stage_plan import StagePlan
from packaging.runtime import get_default_target, get_target
from packaging.runtime.contracts import call_optional_target_hook


@dataclass(frozen=True)
class StageBuildResult:
    payload: dict[str, Any]
    stage_plan: StagePlan


def run_stage_pipeline(
    staging_root: Path,
    *,
    runtime_dir: Optional[str] = None,
    target_name: Optional[str] = None,
    skills_plan_json: Optional[str] = None,
) -> StageBuildResult:
    target = get_target(target_name) if target_name else get_default_target()
    if staging_root.exists() and any(staging_root.iterdir()):
        raise ValueError(f"staging directory must not exist or must be empty: {staging_root}")

    stage_runtime_dir = str(runtime_dir or "").strip()
    if not stage_runtime_dir:
        raise ValueError("runtime_dir is required")
    stage_runtime_dir = call_optional_target_hook(
        target,
        "prepare_runtime_dir",
        stage_runtime_dir,
        default=stage_runtime_dir,
    )

    staging_root.mkdir(parents=True, exist_ok=True)

    stage_plan = target.build_stage_plan(stage_runtime_dir)

    skills_plan_payload = normalize_skills_plan_payload_for_target(
        target,
        load_skills_plan_payload(skills_plan_json=skills_plan_json),
    )
    if isinstance(skills_plan_payload, dict):
        skills_plan_json = json.dumps(skills_plan_payload, ensure_ascii=False)

    agent_type = validate_agent_type(
        skills_plan_payload.get("agent_type") if isinstance(skills_plan_payload, dict) else None,
    )
    has_explicit_selection = has_explicit_selection_groups(skills_plan_payload)

    selection_groups = (
        selection_groups_from_payload(skills_plan_payload)
        if has_explicit_selection
        else None
    )
    selected_skill_paths = None
    if selection_groups is not None:
        selected_skill_paths = {
            str(item.get("path", "")).strip()
            for item in selection_groups.get("skills", [])
            if is_selected_selection_group_item(item)
            and str(item.get("path", "")).strip()
        }
    if agent_type == "download":
        selected_skill_paths_set = set(selected_skill_paths or set())
        if not has_explicit_selection or not selected_skill_paths_set:
            raise ValueError("download agent_type requires explicit --skills-plan with selection_groups.skills")
    mode = get_publish_profile(agent_type)

    bundle_context = (
        {"selection_groups": selection_groups}
        if selection_groups is not None
        else None
    )

    stage_plan = augment_stage_plan_with_selected_symlinks(stage_plan, selected_skill_paths)
    stage_plan = augment_stage_plan_with_selected_external_skill_bindings(
        stage_plan,
        selected_skill_paths=selected_skill_paths,
        skills_plan_json=skills_plan_json,
        target=target,
    )
    extra_tree_sources, extra_file_sources, workspace_documents_manifest_payload = (
        build_confirmed_workspace_document_stage_additions(
            skills_plan_json=skills_plan_json,
            target_name=target_name,
            workspace=stage_runtime_dir,
            agent_type=agent_type,
        )
    )
    stage_plan = StagePlan(
        tree_sources=[*stage_plan.tree_sources, *extra_tree_sources],
        file_sources=[*stage_plan.file_sources, *extra_file_sources],
        metadata={
            **dict(stage_plan.metadata),
            "has_explicit_selection_groups": has_explicit_selection,
            "selection_groups": selection_groups or {},
        },
    )

    workspace_allowlist = None
    if agent_type == "run_online":
        workspace_allowlist = call_optional_target_hook(
            target,
            "build_workspace_allowlist",
            stage_plan=stage_plan,
            default=None,
        )

    payload = mode.stage(
        StageContext(
            staging_root=staging_root,
            stage_plan=stage_plan,
            bundle_context=bundle_context or {},
            selected_skill_paths=selected_skill_paths,
            target=target,
            workspace_documents_manifest_payload=workspace_documents_manifest_payload,
            workspace_allowlist=workspace_allowlist,
        )
    )
    return StageBuildResult(payload=payload, stage_plan=stage_plan)


__all__ = [
    "StageBuildResult",
    "run_stage_pipeline",
]
