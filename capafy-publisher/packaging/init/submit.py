from __future__ import annotations

import json
from typing import Any, Optional

from packaging._shared.common.cli import build_publish_error
from packaging._shared.contracts.selection_groups import (
    RUNTIME_SELECTION_GROUP_KEYS,
    SELECTION_GROUP_KEYS,
    is_selected_selection_group_item,
    normalize_documented_selection_groups,
)
from packaging._shared.platform import create_agent_from_draft, create_version_from_draft
from packaging._shared.runtimes.contracts import call_optional_target_hook
from packaging.runtimes import get_target
from packaging.init.explicit_skill import (
    external_skill_bindings_for_manifest,
    merge_explicit_skill_into_top_level_selections,
)
from packaging.init.selection_discovery import discover_context_selection_groups_for_target


def _invalid_publish_init_input(error: str) -> tuple[dict[str, Any], int]:
    return build_publish_error(
        error=error,
        failed_step="parse_selections_json",
        blocking_category="invalid_publish_init_input",
        developer_next_steps=[
            "Pass selections_json with top-level skills, plugins, and crons arrays.",
            "Rerun publish-init after fixing the selections payload.",
        ],
        next_step="fix_publish_init_input_then_retry",
    ), 1


def _has_selected_skills(selection_groups: dict[str, list[dict[str, Any]]]) -> bool:
    for item in selection_groups.get("skills", []):
        if is_selected_selection_group_item(item):
            return True
    return False


def _merge_discovered_context_selection_groups(
    selection_groups: dict[str, list[dict[str, Any]]],
    discovered_groups: dict[str, list[dict]],
) -> dict[str, list[dict[str, Any]]]:
    merged = {key: list(selection_groups.get(key, [])) for key in SELECTION_GROUP_KEYS}
    key = "workspace_documents"
    seen = {
        str(item.get("path", "")).strip()
        for item in merged.get(key, [])
        if isinstance(item, dict) and str(item.get("path", "")).strip()
    }
    for item in discovered_groups.get(key, []):
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).strip()
        if not path or path in seen:
            continue
        merged[key].append(dict(item))
        seen.add(path)
    return merged


def _selection_groups_with_discovered_context(
    selection_groups: dict[str, list[dict[str, Any]]],
    *,
    env: dict[str, Any],
    resolved_env_id: str,
) -> dict[str, list[dict[str, Any]]]:
    target_name = str(env.get("resolved_target", "") or resolved_env_id).strip() or resolved_env_id
    runtime_dir = str(env.get("runtime_dir", "") or "").strip() or None
    discovered_groups = discover_context_selection_groups_for_target(
        target_name=target_name,
        runtime_dir=runtime_dir,
    )
    return _merge_discovered_context_selection_groups(selection_groups, discovered_groups)


def _parse_publish_init_selections(
    selections_json: str,
    *,
    explicit_skill: Optional[dict[str, Any]],
) -> tuple[Optional[dict[str, Any]], Optional[tuple[dict[str, Any], int]]]:
    try:
        selections = json.loads(selections_json)
    except json.JSONDecodeError as exc:
        return None, (
            build_publish_error(
                error=f"selections_json is not valid JSON: {exc}",
                failed_step="parse_selections_json",
                blocking_category="invalid_publish_init_input",
                developer_next_steps=[
                    "Fix the selections_json syntax and rerun publish-init.",
                ],
                next_step="fix_publish_init_input_then_retry",
            ),
            1,
        )
    if not isinstance(selections, dict):
        return None, (
            build_publish_error(
                error="selections_json must be a JSON object",
                failed_step="parse_selections_json",
                blocking_category="invalid_publish_init_input",
                developer_next_steps=[
                    "Pass selections_json as a JSON object and rerun publish-init.",
                ],
                next_step="fix_publish_init_input_then_retry",
            ),
            1,
        )
    try:
        selections = merge_explicit_skill_into_top_level_selections(selections, explicit_skill)
    except ValueError as exc:
        return None, _invalid_publish_init_input(str(exc))
    return selections, None


def _normalize_runtime_selection_groups(
    selections: dict[str, Any],
) -> tuple[Optional[dict[str, list[dict[str, Any]]]], Optional[tuple[dict[str, Any], int]]]:
    if "workflow_intent" in selections:
        return None, _invalid_publish_init_input("workflow_intent is not accepted in publish-init selections")
    context_keys = [key for key in ("workspace_documents",) if key in selections]
    if context_keys:
        return None, _invalid_publish_init_input(
            f"{', '.join(context_keys)} are not accepted in publish-init selections; "
            "they are discovered after runtime selection and confirmed on the platform page"
        )
    allowed_selection_keys = {"agent_id", "title", "description", *RUNTIME_SELECTION_GROUP_KEYS}
    unsupported_keys = sorted(key for key in selections if key not in allowed_selection_keys)
    if unsupported_keys:
        return None, _invalid_publish_init_input(
            f"{', '.join(unsupported_keys)} are not accepted in publish-init selections"
        )
    missing_runtime_keys = [key for key in RUNTIME_SELECTION_GROUP_KEYS if key not in selections]
    if missing_runtime_keys:
        return None, _invalid_publish_init_input(
            "selections_json must include top-level skills, plugins, and crons arrays"
        )

    raw_runtime_groups: dict[str, Any] = {}
    for key in RUNTIME_SELECTION_GROUP_KEYS:
        value = selections.get(key)
        if not isinstance(value, list):
            return None, _invalid_publish_init_input(f"{key} must be an array")
        for item in value:
            if not isinstance(item, dict):
                return None, _invalid_publish_init_input(f"{key} items must be objects")
        raw_runtime_groups[key] = [
            {
                **{field: field_value for field, field_value in item.items() if field != "selection"},
                "selection": "selected",
            }
            for item in value
        ]
    return normalize_documented_selection_groups(raw_runtime_groups), None


def publish_init_submit(
    *,
    env: dict[str, Any],
    resolved_env_id: str,
    selections_json: str,
    explicit_skill: Optional[dict[str, Any]] = None,
    agent_id: Optional[str] = None,
) -> tuple[dict[str, Any], int]:
    selections, error = _parse_publish_init_selections(
        selections_json,
        explicit_skill=explicit_skill,
    )
    if error is not None:
        return error
    assert selections is not None

    selection_agent_id = selections.get("agent_id") or None
    explicit_agent_id = str(agent_id or "").strip() or None
    if selection_agent_id and explicit_agent_id and str(selection_agent_id).strip() != explicit_agent_id:
        return _invalid_publish_init_input(
            "agent_id in selections_json does not match the CLI --agent-id value"
        )
    final_agent_id = explicit_agent_id or selection_agent_id
    title = str(selections.get("title", "") or "").strip()
    description = str(selections.get("description", "") or "").strip()

    selection_groups, error = _normalize_runtime_selection_groups(selections)
    if error is not None:
        return error
    assert selection_groups is not None

    target = get_target(str(env.get("resolved_target", "") or resolved_env_id).strip() or resolved_env_id)
    selection_groups = call_optional_target_hook(
        target,
        "normalize_selection_groups",
        selection_groups,
        default=selection_groups,
    )
    if not _has_selected_skills(selection_groups):
        return _invalid_publish_init_input(
            "publish-init requires at least one selected skill; "
            "rerun Phase A or ask the creator to confirm the skill to publish"
        )

    try:
        selection_groups = _selection_groups_with_discovered_context(
            selection_groups,
            env=env,
            resolved_env_id=resolved_env_id,
        )
    except ValueError as exc:
        return build_publish_error(
            error=str(exc),
            failed_step="discover_context_sources",
            blocking_category="context_discovery_failed",
            developer_next_steps=[
                "Fix the local workspace document precondition, then rerun publish-init with the same selections.",
            ],
            next_step="fix_context_discovery_then_retry",
        ), 1

    card_draft: dict[str, Any] = {
        "title": title,
        "description": description,
        "environment": {
            "env_id": resolved_env_id,
            "runtime_dir": str(env.get("runtime_dir", "")).strip(),
        },
        "selection_groups": selection_groups,
    }
    if final_agent_id:
        result = create_version_from_draft(final_agent_id, card_draft)
    else:
        result = create_agent_from_draft(card_draft)

    external_skill_bindings = external_skill_bindings_for_manifest(selection_groups)
    payload = {
        "status": "submitted",
        "agent_id": result.get("agentId", ""),
        "agent_version_id": result.get("agentVersionId", ""),
        "review_url": result.get("url", ""),
    }
    if external_skill_bindings:
        payload["external_skill_bindings"] = external_skill_bindings
    return payload, 0


__all__ = ["publish_init_submit"]
