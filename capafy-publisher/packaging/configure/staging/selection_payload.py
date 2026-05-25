from __future__ import annotations
from typing import Optional

import json

from packaging._shared.contracts.selection_groups import (
    is_selected_selection_group_item,
    normalize_documented_selection_groups,
)
from packaging.runtimes import get_target
from packaging._shared.runtimes.contracts import call_optional_target_hook


CANONICAL_SELECTION_GROUPS_KEY = "selection_groups"


def normalize_skills_plan_payload_for_target(target, payload):
    if not isinstance(payload, dict) or CANONICAL_SELECTION_GROUPS_KEY not in payload:
        return payload
    normalized_groups = call_optional_target_hook(
        target,
        "normalize_selection_groups",
        payload.get(CANONICAL_SELECTION_GROUPS_KEY),
        default=payload.get(CANONICAL_SELECTION_GROUPS_KEY),
    )
    if normalized_groups == payload.get(CANONICAL_SELECTION_GROUPS_KEY):
        return payload
    return {
        **payload,
        CANONICAL_SELECTION_GROUPS_KEY: normalized_groups,
    }


def selection_groups_from_payload(
    payload: object,
) -> dict[str, list[dict]]:
    if not isinstance(payload, dict):
        raise ValueError("skills plan top-level value must be an object")
    raw_groups = payload.get(CANONICAL_SELECTION_GROUPS_KEY)
    if not isinstance(raw_groups, dict):
        raise ValueError("skills plan is missing selection_groups")
    normalized = normalize_documented_selection_groups(raw_groups)
    env_id = str(payload.get("env_id", "") or payload.get("resolved_target", "") or "").strip()
    if env_id:
        target = get_target(env_id)
        normalized_payload = normalize_skills_plan_payload_for_target(
            target,
            {CANONICAL_SELECTION_GROUPS_KEY: normalized},
        )
        if isinstance(normalized_payload, dict):
            normalized = normalized_payload[CANONICAL_SELECTION_GROUPS_KEY]
    return normalized


def _selected_group_items(
    payload: object,
    *,
    key: str,
) -> list[dict]:
    groups = selection_groups_from_payload(payload)
    return [
        item
        for item in groups.get(key, [])
        if is_selected_selection_group_item(item)
    ]


def _target_from_payload(payload: object):
    if not isinstance(payload, dict):
        return None
    env_id = str(payload.get("env_id", "") or payload.get("resolved_target", "") or "").strip()
    if not env_id:
        return None
    return get_target(env_id)


def _selected_cron_path(item: dict, *, target=None) -> str:
    path = str(
        call_optional_target_hook(
            target,
            "selected_cron_path_from_selection_item",
            item,
            default="",
        )
        or ""
    ).strip()
    return path


def selected_skill_paths_from_payload(
    payload: object,
) -> set[str]:
    return {
        str(item.get("path", "")).strip()
        for item in _selected_group_items(payload, key="skills")
        if str(item.get("path", "")).strip()
    }


def selected_plugin_paths_from_payload(
    payload: object,
) -> set[str]:
    return {
        str(item.get("path", "")).strip()
        for item in _selected_group_items(payload, key="plugins")
        if str(item.get("path", "")).strip()
    }


def selected_cron_paths_from_payload(
    payload: object,
    *,
    target=None,
) -> set[str]:
    active_target = target if target is not None else _target_from_payload(payload)
    return {
        path
        for item in _selected_group_items(payload, key="crons")
        for path in (_selected_cron_path(item, target=active_target),)
        if path
    }


def load_skills_plan_payload(
    *,
    skills_plan_json: Optional[str] = None,
) -> Optional[object]:
    if not skills_plan_json:
        return None
    try:
        return json.loads(skills_plan_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"skills selection JSON parse failed: {exc}") from exc


def has_explicit_selection_groups(payload: object) -> bool:
    return isinstance(payload, dict) and CANONICAL_SELECTION_GROUPS_KEY in payload


def skills_plan_from_selection_groups(
    selection_groups: dict,
    *,
    agent_type: str = "run_online",
) -> str:
    if not selection_groups:
        return ""
    plan: dict = {
        "agent_type": agent_type,
        "selection_groups": normalize_documented_selection_groups(selection_groups),
    }
    return json.dumps(plan, ensure_ascii=False)


__all__ = [
    "CANONICAL_SELECTION_GROUPS_KEY",
    "has_explicit_selection_groups",
    "load_skills_plan_payload",
    "normalize_skills_plan_payload_for_target",
    "selected_cron_paths_from_payload",
    "selected_plugin_paths_from_payload",
    "selected_skill_paths_from_payload",
    "selection_groups_from_payload",
    "skills_plan_from_selection_groups",
]
