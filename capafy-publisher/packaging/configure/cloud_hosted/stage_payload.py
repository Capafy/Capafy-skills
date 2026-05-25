from __future__ import annotations

from pathlib import Path
from typing import Any, Optional


def build_cloud_hosted_stage_payload(
    *,
    staging_root: Path,
    sources: dict[str, str],
    copied_files: int,
    skipped: list[str],
    included_skills: list[dict],
    suspicious_skills: list[dict],
    excluded_credential_files: list[str],
    bundle_context_path: Path,
    runtime_dependencies_path: Path,
    runtime_environment_path: Path,
    stage_manifest_path: Path,
    selected_units_manifest_path: Optional[Path],
    workspace_documents_manifest_path: Optional[Path] = None,
    selected_skill_paths: Optional[set[str]],
    selected_plugin_paths: Optional[set[str]],
    selected_cron_paths: Optional[set[str]],
    runtime_validation_target: str,
    postprocess_summary: dict[str, Any],
    main_tree_redaction_summary: dict[str, int],
) -> dict[str, Any]:
    normalized_selected_paths = set(selected_skill_paths or set())
    normalized_plugin_paths = set(selected_plugin_paths or set())
    normalized_cron_paths = set(selected_cron_paths or set())
    public_selected_skill_paths = sorted(
        normalized_selected_paths - normalized_plugin_paths - normalized_cron_paths
    )

    payload: dict[str, Any] = {
        "agent_type": "run_online",
        "staging_path": str(staging_root),
        "sources": sources,
        "copied_files": copied_files,
        "skipped": skipped,
        "included_skills": included_skills,
        "suspicious_skills": suspicious_skills,
        "excluded_credential_files": excluded_credential_files,
        "generated_files": [
            bundle_context_path.name,
            runtime_dependencies_path.name,
            runtime_environment_path.name,
        ],
        "bundle_context_path": str(bundle_context_path),
        "runtime_dependencies_path": str(runtime_dependencies_path),
        "runtime_environment_path": str(runtime_environment_path),
        "stage_manifest_path": str(stage_manifest_path),
    }
    if selected_units_manifest_path is not None:
        payload["generated_files"].insert(1, selected_units_manifest_path.name)
        payload["selected_units_manifest_path"] = str(selected_units_manifest_path)
    if workspace_documents_manifest_path is not None:
        payload["generated_files"].append(workspace_documents_manifest_path.name)
        payload["workspace_documents_manifest_path"] = str(workspace_documents_manifest_path)
    if selected_skill_paths is not None:
        payload["selected_skill_paths"] = public_selected_skill_paths
    if selected_plugin_paths is not None:
        payload["selected_plugin_paths"] = sorted(normalized_plugin_paths)
    if selected_cron_paths is not None:
        payload["selected_cron_paths"] = sorted(normalized_cron_paths)
    if runtime_validation_target:
        payload["runtime_validation_target"] = runtime_validation_target
    payload.update(postprocess_summary)
    payload.update(
        {
            "main_tree_local_path_files_redacted": main_tree_redaction_summary["processed_file_count"],
            "main_tree_local_path_redactions": main_tree_redaction_summary["total_replacements"],
        }
    )
    return payload


__all__ = ["build_cloud_hosted_stage_payload"]
