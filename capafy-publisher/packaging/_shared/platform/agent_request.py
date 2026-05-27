from __future__ import annotations

import json
from typing import Any

from capafy_platform import runtime_context
from packaging._shared.common.url_values import has_http_url_scheme
from packaging._shared.platform.runtime_mapping import (
    documented_agent_runtime_from_values,
    normalize_agent_type,
)
from packaging._shared.contracts.selection_groups import (
    SELECTION_GROUP_KEYS,
    is_selected_selection_group_item,
    normalize_documented_selection_groups,
)


_OPTIONAL_CREATE_AGENT_FIELDS = ("tags",)

LM_GENERATED_TITLE_NOTICE = "(LM generated — please review and edit before saving)"


def _platform_upload_title(title: Any) -> str:
    normalized = str(title or "").strip()
    if normalized.endswith(LM_GENERATED_TITLE_NOTICE):
        return normalized
    return f"{normalized} {LM_GENERATED_TITLE_NOTICE}".strip()


def _draft_selection_groups(card_draft: dict) -> dict[str, list[dict[str, Any]]]:
    raw_groups = card_draft.get("selection_groups")
    if raw_groups is not None and not isinstance(raw_groups, dict):
        raise ValueError("card_draft.selection_groups must be an object")
    if isinstance(raw_groups, dict):
        for key in SELECTION_GROUP_KEYS:
            if key not in raw_groups:
                continue
            value = raw_groups.get(key)
            if not isinstance(value, list):
                raise ValueError(f"card_draft.selection_groups.{key} must be an array")
            for item in value:
                if not isinstance(item, dict):
                    raise ValueError(f"card_draft.selection_groups.{key} items must be objects")
    return normalize_documented_selection_groups(raw_groups)


def _validate_selected_only_selection_groups(selection_groups: dict[str, list[dict[str, Any]]]) -> None:
    rejected: list[str] = []
    for key in SELECTION_GROUP_KEYS:
        for item in selection_groups.get(key, []):
            if is_selected_selection_group_item(item):
                continue

            identifier = str(item.get("path") or item.get("id") or item.get("name") or "").strip() or "<unknown>"
            rejected.append(f"{key}:{identifier}")
    if rejected:
        sample = ", ".join(rejected[:3])
        raise ValueError(
            "card_draft.selection_groups must already be selected-only before platform upload"
            f": {sample}"
        )


def _validated_upload_selection_groups(card_draft: dict) -> dict[str, list[dict[str, Any]]]:
    normalized = _draft_selection_groups(card_draft)
    _validate_selected_only_selection_groups(normalized)
    return _strip_local_workspace_skill_sources(normalized)


def _strip_local_workspace_skill_sources(
    selection_groups: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    groups = {key: list(selection_groups.get(key, [])) for key in SELECTION_GROUP_KEYS}
    skills: list[dict[str, Any]] = []
    for item in groups.get("skills", []):
        normalized = dict(item)
        binding_kind = str(normalized.get("binding_kind", "")).strip()
        if binding_kind == "workspace_skill_dir":
            normalized.pop("source_path", None)
            normalized.pop("source_root", None)
            normalized.pop("binding_kind", None)
        skills.append(normalized)
    groups["skills"] = skills
    return groups


def _raw_environment_payload(card_draft: dict) -> dict[str, Any]:
    raw = card_draft.get("environment", {})
    if not isinstance(raw, dict):
        raise ValueError("card_draft.environment must be an object")
    return raw


def _documented_agent_runtime(card_draft: dict) -> str:
    environment = _raw_environment_payload(card_draft)
    return documented_agent_runtime_from_values(
        environment.get("env_id", ""),
        environment.get("resolved_target", ""),
    )


def _platform_agent_type(card_draft: dict) -> str:
    return normalize_agent_type(card_draft.get("agent_type", ""))


def _build_workflow_info_payload(card_draft: dict) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "selection_groups": _validated_upload_selection_groups(card_draft),
    }
    skill_version = runtime_context.load_app_version()
    if skill_version:
        payload["skill_version"] = skill_version
    description = str(card_draft.get("description", "") or "").strip()
    if description:
        payload["description"] = description
    return payload


def build_agent_create_request(card_draft: dict) -> dict[str, Any]:
    platform_agent_type = _platform_agent_type(card_draft)
    payload: dict[str, Any] = {
        "title": _platform_upload_title(card_draft.get("title", "")),
        "agentType": platform_agent_type,
        "bizType": platform_agent_type,
        "workflowInfo": json.dumps(_build_workflow_info_payload(card_draft), ensure_ascii=False),
    }
    description = str(card_draft.get("description", "") or "").strip()
    if description:
        payload["shortDescription"] = description
    documented_agent_runtime = _documented_agent_runtime(card_draft)
    if documented_agent_runtime:
        payload["agentRuntime"] = documented_agent_runtime

    for field in _OPTIONAL_CREATE_AGENT_FIELDS:
        value = card_draft.get(field)
        if value is None:
            continue
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                continue
            payload[field] = stripped
            continue
        payload[field] = value
    return payload


def build_agent_version_create_request(agent_id: str, card_draft: dict) -> dict[str, Any]:
    resolved_agent_id = str(agent_id or "").strip()
    if not resolved_agent_id:
        raise ValueError("agent_id must not be empty")
    platform_agent_type = _platform_agent_type(card_draft)
    payload = {
        "agentId": resolved_agent_id,
        "agentType": platform_agent_type,
        "bizType": platform_agent_type,
        "workflowInfo": json.dumps(_build_workflow_info_payload(card_draft), ensure_ascii=False),
    }
    documented_agent_runtime = _documented_agent_runtime(card_draft)
    if documented_agent_runtime:
        payload["agentRuntime"] = documented_agent_runtime
    return payload


def build_package_report_request(
    agent_version_id: str,
    package_url: str,
) -> dict[str, Any]:
    version_id = str(agent_version_id or "").strip()
    if not version_id:
        raise ValueError("agent_version_id must not be empty")
    url = str(package_url or "").strip()
    if not url:
        raise ValueError("package_url must not be empty")
    if not has_http_url_scheme(url):
        raise ValueError("package_url must be an absolute http(s) URL")
    return {
        "agentVersionId": version_id,
        "packageUrl": url,
    }


__all__ = [
    "build_agent_create_request",
    "build_agent_version_create_request",
    "build_package_report_request",
]
