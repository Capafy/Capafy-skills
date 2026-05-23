from __future__ import annotations

import json

from packaging._shared.contracts.selection_groups import (
    is_selected_selection_group_item,
    normalize_documented_selection_groups,
)

CATEGORY_NAMES = (
    "workspace_documents",
    "excluded_sources",
)
SELECTED_CATEGORIES = (
    "workspace_documents",
)


def load_payload(
    *,
    skills_plan_json: str | None,
) -> dict:
    if not skills_plan_json:
        return {}
    try:
        payload = json.loads(skills_plan_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"confirmed workspace documents payload parse failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("confirmed workspace documents payload top-level value must be an object")
    return payload


def normalize_payload_categories(payload: object) -> dict[str, list]:
    if not isinstance(payload, dict):
        raise ValueError("confirmed workspace documents payload top-level value must be an object")
    normalized: dict[str, list] = {}
    for category in CATEGORY_NAMES:
        value = payload.get(category, [])
        if not isinstance(value, list):
            raise ValueError(f"{category} must be an array")
        for item in value:
            if not isinstance(item, (str, dict)):
                raise ValueError(f"{category} items must be strings or objects")
            if isinstance(item, dict):
                raw_path = item.get("path")
                if not isinstance(raw_path, str):
                    if raw_path is None:
                        raise ValueError(f"{category} item objects must include a non-empty path")
                    raise ValueError(f"{category} item path must be a string")
                if not raw_path.strip():
                    raise ValueError(f"{category} item objects must include a non-empty path")
        normalized[category] = value
    return normalized


def load_confirmed_workspace_documents_payload(
    *,
    skills_plan_json: str | None,
) -> dict:
    payload = load_payload(skills_plan_json=skills_plan_json)
    raw_groups = payload.get("selection_groups", {}) if isinstance(payload, dict) else {}
    if raw_groups is None:
        raw_groups = {}
    if not isinstance(raw_groups, dict):
        raise ValueError("selection_groups must be an object")
    for key in ("workspace_documents",):
        value = raw_groups.get(key, [])
        if not isinstance(value, list):
            raise ValueError(f"selection_groups.{key} must be an array")
        for item in value:
            if not isinstance(item, dict):
                raise ValueError(f"selection_groups.{key} items must be objects")
            raw_path = item.get("path")
            if not isinstance(raw_path, str):
                if raw_path is None:
                    raise ValueError(f"selection_groups.{key} item objects must include a non-empty path")
                raise ValueError(f"selection_groups.{key} item path must be a string")
            if not raw_path.strip():
                raise ValueError(f"selection_groups.{key} item objects must include a non-empty path")
    groups = normalize_documented_selection_groups(raw_groups)

    workspace_documents = [
        item
        for item in groups.get("workspace_documents", [])
        if is_selected_selection_group_item(item)
    ]
    excluded_sources = [
        item
        for key in ("workspace_documents",)
        for item in groups.get(key, [])
        if not is_selected_selection_group_item(item)
    ]
    return normalize_payload_categories(
        {
            "workspace_documents": workspace_documents,
            "excluded_sources": excluded_sources,
        }
    )


__all__ = [
    "CATEGORY_NAMES",
    "SELECTED_CATEGORIES",
    "load_confirmed_workspace_documents_payload",
    "load_payload",
    "normalize_payload_categories",
]
