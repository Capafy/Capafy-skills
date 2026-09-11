from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from packaging.common.fs import record_skip
from packaging.common.packaged_files import should_skip_packaged_path
from packaging.publish.artifacts.bundle_context import write_bundle_context
from packaging.publish.staging.manifest import write_stage_manifest
from packaging.publish.artifacts.path_refs import build_packaged_path_refs
from packaging.runtime.contracts import call_optional_target_hook
from packaging.publish.selection.inventory import build_skill_inventory
from packaging.publish.profiles.run_online.tree_copy import (
    StageCopyState,
    StageTreeCopyRequest,
    copy_stage_tree as _copy_stage_tree,
)
from packaging.publish.profiles.run_online.runtime_dependencies import (
    write_runtime_dependencies_manifest,
)
from packaging.publish.domain.contexts import StageContext
from packaging.publish.selection.confirmed_workspace_documents import (
    write_confirmed_workspace_documents_manifest,
)
from packaging.publish.staging.exclusions import (
    should_skip_high_risk_stage_file as _should_skip_high_risk_stage_file,
    validate_staging_high_risk_boundary,
)
from packaging.publish.staging.local_path_cleanup import redact_main_tree_local_paths
from packaging.publish.staging.markdown_references import stage_direct_markdown_file_references
from packaging.publish.staging.tree_copy import copy_tree_file


def build_cloud_hosted_stage_payload(
    *,
    staging_root: Path,
    sources: dict[str, str],
    copied_files: int,
    skipped: list[str],
    included_skills: list[dict],
    suspicious_skills: list[dict],
    bundle_context_path: Path,
    runtime_dependencies_path: Path,
    stage_manifest_path: Path,
    workspace_documents_manifest_path: Optional[Path] = None,
    selected_skill_paths: Optional[set[str]],
    main_tree_redaction_summary: dict[str, int],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "agent_type": "run_online",
        "staging_path": str(staging_root),
        "sources": sources,
        "copied_files": copied_files,
        "skipped": skipped,
        "included_skills": included_skills,
        "suspicious_skills": suspicious_skills,
        "generated_files": [
            bundle_context_path.name,
            runtime_dependencies_path.name,
        ],
        "bundle_context_path": str(bundle_context_path),
        "runtime_dependencies_path": str(runtime_dependencies_path),
        "stage_manifest_path": str(stage_manifest_path),
    }
    if workspace_documents_manifest_path is not None:
        payload["generated_files"].append(workspace_documents_manifest_path.name)
        payload["workspace_documents_manifest_path"] = str(workspace_documents_manifest_path)
    if selected_skill_paths is not None:
        payload["selected_skill_paths"] = sorted(selected_skill_paths)
    payload.update(
        {
            "main_tree_local_path_files_redacted": main_tree_redaction_summary[
                "processed_file_count"
            ],
            "main_tree_local_path_redactions": main_tree_redaction_summary["total_replacements"],
        }
    )
    return payload


def _cloud_workspace_excluded_prefixes(target, tree_source) -> tuple[str, ...]:
    return tuple(
        call_optional_target_hook(
            target,
            "cloud_workspace_excluded_prefixes",
            tree_source,
            default=(),
        )
    )


def _cloud_workspace_allowlist(target, tree_source, workspace_allowlist):
    return call_optional_target_hook(
        target,
        "cloud_workspace_allowlist",
        tree_source,
        workspace_allowlist,
        default=None,
    )


def _should_report_public_stage_source(*, source_value: str) -> bool:
    return source_value != "scan_only_reference"


def _collect_missing_stage_sources(stage_plan) -> list[str]:
    missing_sources: list[str] = []
    for tree_source in getattr(stage_plan, "tree_sources", []):
        source_root = tree_source.source_root.expanduser()
        if not getattr(tree_source, "required", True) and not source_root.is_dir():
            continue
        if not source_root.is_dir():
            missing_sources.append(str(source_root))
    for file_source in getattr(stage_plan, "file_sources", []):
        source_file = file_source.source_file.expanduser()
        if not getattr(file_source, "required", True) and not source_file.is_file():
            continue
        if not source_file.is_file():
            missing_sources.append(str(source_file))
    return missing_sources


def stage_cloud_hosted(
    ctx: StageContext,
) -> dict:
    staging_root = ctx.staging_root
    stage_plan = ctx.stage_plan
    bundle_context = ctx.bundle_context
    selected_skill_paths = (
        {
            str(path).strip().rstrip("/")
            for path in ctx.selected_skill_paths
            if str(path).strip()
        }
        if ctx.selected_skill_paths is not None
        else None
    )
    workspace_allowlist = ctx.workspace_allowlist
    target = ctx.target
    workspace_documents_manifest_payload = ctx.workspace_documents_manifest_payload

    missing_sources = _collect_missing_stage_sources(stage_plan)
    if missing_sources:
        joined = ", ".join(missing_sources)
        raise ValueError(f"missing stage sources: {joined}")
    copied_files = 0
    copy_state = StageCopyState()
    sources: dict[str, str] = {}
    scan_only_prefixes: list[str] = []
    for tree_source in stage_plan.tree_sources:
        source_root = tree_source.source_root.expanduser()
        if not getattr(tree_source, "required", True) and not source_root.is_dir():
            continue

        if getattr(tree_source, "scan_only", False):
            display_prefix = str(tree_source.display_prefix).strip().rstrip("/")
            if display_prefix:
                scan_only_prefixes.append(display_prefix)
            continue

        effective_excluded_prefixes = (
            *tree_source.excluded_relpath_prefixes,
            *_cloud_workspace_excluded_prefixes(target, tree_source),
        )
        copied_files += _copy_stage_tree(
            StageTreeCopyRequest(
                source_root=source_root.resolve(),
                target_root=staging_root / tree_source.relative_target_root,
                staging_root=staging_root,
                display_prefix=tree_source.display_prefix,
                skip_skill_runtime_outputs=tree_source.skip_skill_runtime_outputs,
                excluded_relpath_prefixes=effective_excluded_prefixes,
                selected_paths=selected_skill_paths,
                workspace_allowlist=_cloud_workspace_allowlist(target, tree_source, workspace_allowlist),
                target=target,
                stage_plan=stage_plan,
            ),
            copy_state,
        )
        source_key = str(tree_source.source_key).strip()
        source_value = str(tree_source.source_value).strip()
        if _should_report_public_stage_source(source_value=source_value):
            sources[source_key] = source_value

    for file_source in stage_plan.file_sources:
        source_file = file_source.source_file.expanduser()
        if not getattr(file_source, "required", True) and not source_file.is_file():
            continue
        target_relpath = file_source.relative_target_path.as_posix()
        if getattr(file_source, "requires_user_confirmation", False):
            continue
        if getattr(file_source, "scan_only", False):
            normalized_relpath = target_relpath.rstrip("/")
            if normalized_relpath:
                scan_only_prefixes.append(normalized_relpath)
            continue
        high_risk_stage_file = _should_skip_high_risk_stage_file(target, target_relpath)
        if should_skip_packaged_path(source_file, target_relpath, is_dir=False) or high_risk_stage_file:
            record_skip(copy_state.skipped, copy_state.skipped_seen, target_relpath, is_dir=False)
            continue
        target_file = staging_root / file_source.relative_target_path
        copy_tree_file(source_file, target_file)
        copied_files += 1
        copied_files += stage_direct_markdown_file_references(
            source_file,
            target_file,
            staging_root=staging_root,
            target=target,
            stage_plan=stage_plan,
        )
        source_key = str(file_source.source_key).strip()
        source_value = str(file_source.source_value).strip()
        if _should_report_public_stage_source(source_value=source_value):
            sources[source_key] = source_value

    runtime_dependencies_path = write_runtime_dependencies_manifest(staging_root)
    included_skills, suspicious_skills = build_skill_inventory(
        staging_root,
        target=target,
    )
    if selected_skill_paths:
        call_optional_target_hook(
            target,
            "validate_selected_skills",
            selected_paths=selected_skill_paths,
            included_skills=included_skills,
        )
    bundle_context_path = write_bundle_context(
        staging_root,
        bundle_context,
    )
    workspace_documents_manifest_path = write_confirmed_workspace_documents_manifest(
        staging_root,
        workspace_documents_manifest_payload,
    )
    main_tree_redaction_summary = redact_main_tree_local_paths(
        staging_root,
        packaged_path_refs=build_packaged_path_refs(workspace_documents_manifest_payload or {}),
    )
    validate_staging_high_risk_boundary(target, staging_root)

    stage_manifest_path = write_stage_manifest(
        staging_root,
        scan_only_prefixes=tuple(dict.fromkeys(scan_only_prefixes)),
    )

    return build_cloud_hosted_stage_payload(
        staging_root=staging_root,
        sources=sources,
        copied_files=copied_files,
        skipped=copy_state.skipped,
        included_skills=included_skills,
        suspicious_skills=suspicious_skills,
        bundle_context_path=bundle_context_path,
        runtime_dependencies_path=runtime_dependencies_path,
        stage_manifest_path=stage_manifest_path,
        workspace_documents_manifest_path=workspace_documents_manifest_path,
        selected_skill_paths=selected_skill_paths,
        main_tree_redaction_summary=main_tree_redaction_summary,
    )


__all__ = [
    "build_cloud_hosted_stage_payload",
    "stage_cloud_hosted",
]
