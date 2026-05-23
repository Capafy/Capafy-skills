from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from packaging._shared.common.fs import record_skip
from packaging._shared.common.packaged_files import should_skip_packaged_path
from packaging._shared.common.exclusion_rules import exclude_reason_code_for_path
from packaging.configure.cloud_hosted.no_auth import (
    build_workflow_related_no_auth_paths,
    selected_workflow_unit_paths,
)
from packaging.configure.cloud_hosted.tree_copy import (
    StageCopyState,
    StageTreeCopyRequest,
    copy_stage_tree as _copy_stage_tree,
)
from packaging.configure.cloud_hosted.stage_payload import build_cloud_hosted_stage_payload
from packaging.configure.staging.tree_copy import copy_tree_file
from packaging.configure.staging.markdown_references import stage_direct_markdown_file_references
from packaging.configure.staging.local_path_cleanup import redact_main_tree_local_paths
from packaging._shared.policies.path_refs import build_packaged_path_refs
from packaging._shared.contracts.bundle_context import write_bundle_context
from packaging.configure.exclusion.stage import (
    scan_only_excluded_credential_relpath as _scan_only_excluded_credential_relpath,
    should_skip_high_risk_stage_file as _should_skip_high_risk_stage_file,
)
from packaging._shared.contracts.stage_manifest import write_stage_manifest
from packaging.configure.cloud_hosted.runtime_manifest import (
    write_runtime_dependencies_manifest,
    write_runtime_environment_manifest,
)
from packaging.configure.staging.review import compute_scan_only_digest, compute_staging_digest
from packaging.configure.selection.inventory import build_skill_inventory
from packaging.configure.selection.units_manifest import write_selected_units_manifest
from packaging.configure.selection.confirmed_workspace_documents import write_confirmed_workspace_documents_manifest
from packaging.configure.contexts import StageContext
from packaging.runtimes import get_target
from packaging._shared.runtimes.contracts import call_optional_target_hook


_CLOUD_WORKSPACE_EXCLUDED_PREFIXES = (
    ".pytest_cache",
    "dev/tests",
)
_OPENCLAW_WORKSPACE_SOURCE_KEY = ".openclaw/workspace"


def _cloud_workspace_excluded_prefixes(display_prefix: str) -> tuple[str, ...]:
    normalized = str(display_prefix or "").strip().rstrip("/")
    if normalized.startswith(_OPENCLAW_WORKSPACE_SOURCE_KEY):
        return _CLOUD_WORKSPACE_EXCLUDED_PREFIXES
    return ()


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
    selected_skill_paths = ctx.selected_skill_paths
    selected_plugin_paths = ctx.selected_plugin_paths
    selected_cron_paths = ctx.selected_cron_paths
    workspace_allowlist = ctx.workspace_allowlist
    target = ctx.target
    workspace_documents_manifest_payload = ctx.workspace_documents_manifest_payload

    missing_sources = _collect_missing_stage_sources(stage_plan)
    if missing_sources:
        joined = ", ".join(missing_sources)
        raise ValueError(f"missing stage sources: {joined}")
    copied_files = 0
    copy_state = StageCopyState()
    explicit_excluded_credential_files: set[str] = set()
    sources: dict[str, str] = {}
    scan_only_prefixes: list[str] = []
    scan_only_source_map: dict[str, str] = {}
    selected_unit_paths: set[str] | None = None
    if any(group is not None for group in (selected_skill_paths, selected_plugin_paths, selected_cron_paths)):

        selected_unit_paths = selected_workflow_unit_paths(
            selected_skill_paths=selected_skill_paths,
            selected_plugin_paths=selected_plugin_paths,
            selected_cron_paths=selected_cron_paths,
        )

    for tree_source in stage_plan.tree_sources:
        source_root = tree_source.source_root.expanduser()
        if not getattr(tree_source, "required", True) and not source_root.is_dir():
            continue

        effective_excluded_prefixes = (
            *tree_source.excluded_relpath_prefixes,
            *_cloud_workspace_excluded_prefixes(tree_source.display_prefix),
        )
        copied_files += _copy_stage_tree(
            StageTreeCopyRequest(
                source_root=source_root.resolve(),
                target_root=staging_root / tree_source.relative_target_root,
                display_prefix=tree_source.display_prefix,
                skip_skill_runtime_outputs=tree_source.skip_skill_runtime_outputs,
                skill_runtime_prefixes=tree_source.skill_runtime_prefixes,
                excluded_relpath_prefixes=effective_excluded_prefixes,
                selected_paths=selected_unit_paths,
                selected_skill_paths=selected_skill_paths,
                selected_plugin_paths=selected_plugin_paths,
                workspace_allowlist=(
                    workspace_allowlist
                    if tree_source.source_key == _OPENCLAW_WORKSPACE_SOURCE_KEY
                    else None
                ),
                apply_selection_filters=not getattr(tree_source, "scan_only", False),
                skip_high_risk_files=not getattr(tree_source, "scan_only", False),
                target=target,
                stage_plan=stage_plan,
            ),
            copy_state,
        )
        source_key = str(tree_source.source_key).strip()
        source_value = str(tree_source.source_value).strip()
        if getattr(tree_source, "scan_only", False):

            display_prefix = str(tree_source.display_prefix).strip().rstrip("/")
            if display_prefix:
                scan_only_prefixes.append(display_prefix)
                scan_only_source_map[display_prefix] = str(source_root)
        if _should_report_public_stage_source(source_value=source_value):
            sources[source_key] = source_value

    for file_source in stage_plan.file_sources:
        source_file = file_source.source_file.expanduser()
        if not getattr(file_source, "required", True) and not source_file.is_file():
            continue
        target_relpath = file_source.relative_target_path.as_posix()
        if getattr(file_source, "requires_user_confirmation", False):
            continue
        high_risk_stage_file = _should_skip_high_risk_stage_file(target, target_relpath)
        if not getattr(file_source, "scan_only", False) and (
            should_skip_packaged_path(source_file, target_relpath, is_dir=False)
            or high_risk_stage_file
        ):
            record_skip(copy_state.skipped, copy_state.skipped_seen, target_relpath, is_dir=False)
            if high_risk_stage_file or exclude_reason_code_for_path(target_relpath) is not None:
                copy_state.excluded_credential_files.add(target_relpath)
            if exclude_reason_code_for_path(target_relpath) is not None:

                explicit_excluded_credential_files.add(target_relpath)
            continue
        target_file = staging_root / file_source.relative_target_path
        copy_tree_file(source_file, target_file)
        copied_files += 1
        copied_files += stage_direct_markdown_file_references(
            source_file,
            target_file,
            stage_plan=stage_plan,
        )
        source_key = str(file_source.source_key).strip()
        source_value = str(file_source.source_value).strip()
        if getattr(file_source, "scan_only", False):
            normalized_relpath = target_relpath.rstrip("/")
            if normalized_relpath:
                scan_only_prefixes.append(normalized_relpath)
                scan_only_source_map[normalized_relpath] = str(source_file)
                excluded_relpath = _scan_only_excluded_credential_relpath(normalized_relpath, target=target)
                if excluded_relpath:
                    explicit_excluded_credential_files.add(excluded_relpath)
        if _should_report_public_stage_source(source_value=source_value):
            sources[source_key] = source_value

    runtime_dependencies_path = write_runtime_dependencies_manifest(staging_root)
    postprocess_summary = call_optional_target_hook(
        target,
        "finalize_packaging",
        staging_root,
        stage_plan,
        agent_type="run_online",
        workspace_documents_manifest_payload=workspace_documents_manifest_payload,
        default={},
    )

    runtime_environment_payload = dict(target.collect_runtime_environment_fields())
    runtime_validation_target = str(postprocess_summary.get("runtime_validation_target", "")).strip()
    if runtime_validation_target:

        validation_target = get_target(runtime_validation_target)
        runtime_environment_payload.update(validation_target.collect_runtime_environment_fields())
    runtime_environment_path = write_runtime_environment_manifest(
        staging_root,
        extra_payload=runtime_environment_payload,
    )
    included_skills, suspicious_skills = build_skill_inventory(
        staging_root,
        target=target,
    )
    selection_runtime_validation = {}
    normalized_all_selected_paths = selected_workflow_unit_paths(
        selected_skill_paths=selected_skill_paths,
        selected_plugin_paths=selected_plugin_paths,
        selected_cron_paths=selected_cron_paths,
    )
    if normalized_all_selected_paths:
        selection_runtime_validation = call_optional_target_hook(
            target,
            "build_selection_runtime_validation",
            selected_paths=normalized_all_selected_paths,
            included_skills=included_skills,
            default={},
        )
    selection_runtime_summary = call_optional_target_hook(
        target,
        "sync_confirmed_skill_entries",
        staging_root,
        selection_runtime_validation,
        default={},
    )
    if isinstance(selection_runtime_summary, dict):
        postprocess_summary.update(selection_runtime_summary)
    bundle_context_path = write_bundle_context(
        staging_root,
        bundle_context,
    )
    selected_units_manifest_path = write_selected_units_manifest(
        staging_root,
        selected_skill_paths=selected_skill_paths,
        selected_plugin_paths=selected_plugin_paths,
        selected_cron_paths=selected_cron_paths,
        runtime_validation=selection_runtime_validation,
    )
    workspace_documents_manifest_path = write_confirmed_workspace_documents_manifest(
        staging_root,
        workspace_documents_manifest_payload,
    )
    main_tree_redaction_summary = redact_main_tree_local_paths(
        staging_root,
        target_name=str(stage_plan.metadata.get("env_id", "")).strip(),
        packaged_path_refs=build_packaged_path_refs(workspace_documents_manifest_payload or {}),
    )

    excluded_credential_files = sorted(

        set(
            build_workflow_related_no_auth_paths(
                copy_state.skipped,
                selected_skill_paths=selected_skill_paths,
                selected_plugin_paths=selected_plugin_paths,
                selected_cron_paths=selected_cron_paths,
                bundle_context=bundle_context,
                stage_plan=stage_plan,
                target=target,
            )
        )
        | explicit_excluded_credential_files
    )
    manifest_excluded_credential_files = sorted(
        set(excluded_credential_files)
        | copy_state.excluded_credential_files
    )
    stage_manifest_path = write_stage_manifest(
        staging_root,
        scan_only_prefixes=tuple(dict.fromkeys(scan_only_prefixes)),
        scan_only_source_map=scan_only_source_map,
        staging_digest=compute_staging_digest(staging_root),
        scan_only_digest=compute_scan_only_digest(staging_root),
        generated_at=datetime.now(timezone.utc).isoformat(),
        excluded_credential_files=tuple(manifest_excluded_credential_files),
    )

    return build_cloud_hosted_stage_payload(
        staging_root=staging_root,
        sources=sources,
        copied_files=copied_files,
        skipped=copy_state.skipped,
        included_skills=included_skills,
        suspicious_skills=suspicious_skills,
        excluded_credential_files=excluded_credential_files,
        bundle_context_path=bundle_context_path,
        runtime_dependencies_path=runtime_dependencies_path,
        runtime_environment_path=runtime_environment_path,
        stage_manifest_path=stage_manifest_path,
        selected_units_manifest_path=selected_units_manifest_path,
        workspace_documents_manifest_path=workspace_documents_manifest_path,
        selected_skill_paths=selected_skill_paths,
        selected_plugin_paths=selected_plugin_paths,
        selected_cron_paths=selected_cron_paths,
        runtime_validation_target=runtime_validation_target,
        postprocess_summary=postprocess_summary,
        main_tree_redaction_summary=main_tree_redaction_summary,
    )


__all__ = ["stage_cloud_hosted"]
