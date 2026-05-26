from __future__ import annotations
from typing import Optional

import json
from pathlib import Path

from packaging._shared.contracts.stage_plan import StagePlan
from packaging._shared.runtimes.support import collect_optional_command_first_line
from packaging._shared.openclaw.config import (
    rewrite_packaged_extra_skill_dirs,
    rewrite_packaged_workspace_document_refs,
    rewrite_packaged_openclaw_config_as_overlay,
    rewrite_packaged_workspace_ref,
    validate_packaged_workspace_document_refs,
)
from packaging.configure.runtimes.openclaw.provider_rewrite import (
    rewrite_openclaw_builtin_models_as_explicit_providers,
)
from packaging.configure.staging.env_preprocess import RuntimeEnvContext
from packaging.configure.runtimes.openclaw.cron_postprocess import clean_cron_jobs, filter_selected_cron_jobs
from .plugin_config import prune_unbundled_local_plugin_config
from .redaction import redact_openclaw_local_configs


def postprocess_stage(
    staging_root: Path,
    stage_plan: StagePlan,
    *,
    agent_type: str = "",
    workspace_documents_manifest_payload: Optional[dict] = None,
) -> dict[str, int]:
    openclaw_config = staging_root / ".openclaw" / "openclaw.json"
    redactions = 0
    builtin_provider_rewrites = 0
    pruned_plugin_configs = 0
    overlay_trimmed_fields = 0
    extra_skill_dir_rewrites = 0
    packaged_workspace_name = None
    if openclaw_config.is_file():
        redactions = redact_openclaw_local_configs(openclaw_config)
        if agent_type == "run_online":
            original_text = openclaw_config.read_text(encoding="utf-8")
            env_context = RuntimeEnvContext(process_env={})
            updated_text, builtin_provider_rewrites = rewrite_openclaw_builtin_models_as_explicit_providers(
                original_text,
                staging_root=staging_root,
                env_context=env_context,
            )
            env_context.apply_staged_dotenv_consumption(staging_root)
            if builtin_provider_rewrites:
                openclaw_config.write_text(updated_text, encoding="utf-8")
    for tree_source in stage_plan.tree_sources:
        if tree_source.source_key != ".openclaw/workspace":
            continue
        candidate = str(tree_source.source_value or "").strip()
        if candidate:
            packaged_workspace_name = candidate
            break
    rewrite_packaged_workspace_ref(staging_root, workspace_name=packaged_workspace_name)
    rewrite_packaged_workspace_document_refs(
        staging_root,
        workspace_documents_manifest_payload=workspace_documents_manifest_payload,
    )
    extra_skill_dir_rewrites = rewrite_packaged_extra_skill_dirs(staging_root, stage_plan)
    source_extensions_root = None
    for tree_source in stage_plan.tree_sources:
        if tree_source.source_key != ".openclaw/extensions":
            continue
        source_extensions_root = tree_source.source_root
        break
    pruned_plugin_configs = prune_unbundled_local_plugin_config(
        staging_root,
        source_extensions_root=source_extensions_root,
    )
    overlay_trimmed_fields = rewrite_packaged_openclaw_config_as_overlay(staging_root)
    selected_cron_jobs_filtered = filter_selected_cron_jobs(staging_root, stage_plan)
    cron_cleaned = clean_cron_jobs(staging_root)
    document_ref_errors = validate_packaged_workspace_document_refs(
        staging_root,
        workspace_documents_manifest_payload=workspace_documents_manifest_payload,
    )
    if document_ref_errors:
        raise ValueError(
            "openclaw workspace document reference validation failed: "
            + "; ".join(document_ref_errors)
        )
    return {
        "openclaw_redactions": redactions,
        "openclaw_builtin_provider_rewrites": builtin_provider_rewrites,
        "openclaw_pruned_plugin_configs": pruned_plugin_configs,
        "openclaw_overlay_trimmed_fields": overlay_trimmed_fields,
        "openclaw_extra_skill_dir_rewrites": extra_skill_dir_rewrites,
        "openclaw_selected_cron_jobs_filtered": selected_cron_jobs_filtered,
        "openclaw_cron_jobs_cleaned": cron_cleaned,
    }


def sync_confirmed_skill_entries(
    staging_root: Path,
    selection_runtime_validation: Optional[dict],
) -> dict[str, int]:
    if not isinstance(selection_runtime_validation, dict):
        return {
            "openclaw_confirmed_skill_entries_synced": 0,
            "openclaw_unconfirmed_skill_entries_removed": 0,
        }

    if "openclaw_confirmed_skills" not in selection_runtime_validation:
        return {
            "openclaw_confirmed_skill_entries_synced": 0,
            "openclaw_unconfirmed_skill_entries_removed": 0,
        }

    raw_items = selection_runtime_validation.get("openclaw_confirmed_skills")
    if not isinstance(raw_items, list):
        return {
            "openclaw_confirmed_skill_entries_synced": 0,
            "openclaw_unconfirmed_skill_entries_removed": 0,
        }

    skill_keys: list[str] = []
    selected_skill_keys: set[str] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        skill_key = str(item.get("skill_key", "") or item.get("name", "")).strip()
        if not skill_key or skill_key in selected_skill_keys:
            continue
        skill_keys.append(skill_key)
        selected_skill_keys.add(skill_key)

    config_path = staging_root / ".openclaw" / "openclaw.json"
    if not config_path.is_file():
        return {
            "openclaw_confirmed_skill_entries_synced": 0,
            "openclaw_unconfirmed_skill_entries_removed": 0,
        }

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "openclaw_confirmed_skill_entries_synced": 0,
            "openclaw_unconfirmed_skill_entries_removed": 0,
        }
    if not isinstance(payload, dict):
        return {
            "openclaw_confirmed_skill_entries_synced": 0,
            "openclaw_unconfirmed_skill_entries_removed": 0,
        }

    skills = payload.get("skills")
    if not isinstance(skills, dict):
        skills = {}
        payload["skills"] = skills

    entries = skills.get("entries")
    if not isinstance(entries, dict):
        entries = {}
        skills["entries"] = entries

    synced = 0
    for skill_key in skill_keys:
        entry = entries.get(skill_key)
        if not isinstance(entry, dict):
            entries[skill_key] = {"enabled": True}
            synced += 1
            continue
        if entry.get("enabled") is not True:
            entry["enabled"] = True
            synced += 1

    removed = 0
    for skill_key in list(entries.keys()):
        if skill_key in selected_skill_keys:
            continue
        entries.pop(skill_key, None)
        removed += 1

    if synced or removed:
        config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "openclaw_confirmed_skill_entries_synced": synced,
        "openclaw_unconfirmed_skill_entries_removed": removed,
    }


def collect_runtime_environment_fields() -> dict[str, Optional[str]]:
    return {
        "openclaw_version": collect_optional_command_first_line(["openclaw", "--version"]),
    }


__all__ = [
    "clean_cron_jobs",
    "collect_runtime_environment_fields",
    "filter_selected_cron_jobs",
    "postprocess_stage",
    "sync_confirmed_skill_entries",
]
