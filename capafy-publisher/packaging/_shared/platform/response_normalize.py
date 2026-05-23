from __future__ import annotations

import json
from typing import Any

from capafy_platform.api import review_url_warnings
from packaging._shared.platform.runtime_mapping import (
    env_id_from_agent_runtime,
)
from packaging._shared.contracts.selection_groups import (
    SELECTION_GROUP_KEYS,
    normalize_documented_selection_groups,
    strip_default_selection_fields,
)
from packaging._shared.contracts.selectable import is_absolute_like_path



_LATEST_VERSION_STABLE_FIELDS = (
    "agentId",
    "agentVersionId",
    "status",
    "agentType",
    "bizType",
    "isConfirmedSkills",
    "isConfirmedConfigKeys",
    "packageUrl",
)

_LATEST_VERSION_NULL_STRING_FIELDS = (
    "agentId",
    "agentVersionId",
    "agentRuntime",
    "agentType",
    "url",
)

_EDIT_LINK_NULL_STRING_FIELDS = (
    "agentVersionId",
    "agentRuntime",
    "url",
)


def _reject_null_string_fields(data: dict[str, Any], fields: tuple[str, ...], *, label: str) -> None:
    for field in fields:
        if field in data and data.get(field) is None:
            raise ValueError(f"platform returned invalid {label}: field {field} must be a string, not null")


def _parse_json_object(value: Any, *, label: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an object or a JSON object string")
    if not value.strip():
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is not a valid JSON object: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} top-level value must be an object")
    return payload


def _require_non_empty_string_field(
    item: dict[str, Any],
    field_name: str,
    *,
    missing_message: str,
    type_message: str,
) -> str:
    value = item.get(field_name)
    if value is None:
        raise ValueError(missing_message)
    if not isinstance(value, str):
        raise ValueError(type_message)
    normalized = value.strip()
    if not normalized:
        raise ValueError(missing_message)
    return normalized


def _validate_optional_typed_field(
    item: dict[str, Any],
    field_name: str,
    *,
    expected_type: type,
    type_message: str,
) -> None:
    if field_name in item and item.get(field_name) is not None and not isinstance(item.get(field_name), expected_type):
        raise ValueError(type_message)


def _validate_cron_selection_group_item(item: dict[str, Any], *, key: str) -> None:
    _require_non_empty_string_field(
        item,
        "id",
        missing_message=f"workflow_info.selection_groups.{key} items must include id",
        type_message=f"workflow_info.selection_groups.{key} item id must be a string",
    )
    _require_non_empty_string_field(
        item,
        "name",
        missing_message=f"workflow_info.selection_groups.{key} items must include name",
        type_message=f"workflow_info.selection_groups.{key} item name must be a string",
    )
    schedule = item.get("schedule")
    if not isinstance(schedule, dict):
        raise ValueError(f"workflow_info.selection_groups.{key} items must include schedule")
    for field_name in ("kind", "expr", "tz"):
        _require_non_empty_string_field(
            schedule,
            field_name,
            missing_message=f"workflow_info.selection_groups.{key} item schedule must include {field_name}",
            type_message=f"workflow_info.selection_groups.{key} item schedule.{field_name} must be a string",
        )
    payload = item.get("payload")
    if not isinstance(payload, dict):
        raise ValueError(f"workflow_info.selection_groups.{key} items must include payload")
    _require_non_empty_string_field(
        payload,
        "prompt",
        missing_message=f"workflow_info.selection_groups.{key} item payload must include prompt",
        type_message=f"workflow_info.selection_groups.{key} item payload.prompt must be a string",
    )


def _normalize_selection_groups_from_workflow_info(
    workflow_info: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    raw_groups = workflow_info.get("selection_groups")
    if "selection_groups" in workflow_info and not isinstance(raw_groups, dict):
        raise ValueError("workflow_info.selection_groups must be an object")
    if isinstance(raw_groups, dict):
        for key in SELECTION_GROUP_KEYS:
            if key not in raw_groups:
                continue
            value = raw_groups.get(key)
            if not isinstance(value, list):
                raise ValueError(f"workflow_info.selection_groups.{key} must be an array")
            for item in value:
                if not isinstance(item, dict):
                    raise ValueError(f"workflow_info.selection_groups.{key} array items must be objects")
                if key == "crons":
                    _validate_cron_selection_group_item(item, key=key)
                    continue
                _require_non_empty_string_field(
                    item,
                    "path",
                    missing_message=f"workflow_info.selection_groups.{key} items must include path",
                    type_message=f"workflow_info.selection_groups.{key} item path must be a string",
                )
                if key in {"skills", "plugins", "workspace_documents"} and is_absolute_like_path(str(item.get("path", ""))):
                    raise ValueError(
                        f"workflow_info.selection_groups.{key} item path must be a logical path, not an absolute path"
                    )
                _validate_optional_typed_field(
                    item,
                    "purpose",
                    expected_type=str,
                    type_message=f"workflow_info.selection_groups.{key} item purpose must be a string",
                )
                _validate_optional_typed_field(
                    item,
                    "requires_user_confirmation",
                    expected_type=bool,
                    type_message=f"workflow_info.selection_groups.{key} item requires_user_confirmation must be a boolean",
                )
    return normalize_documented_selection_groups(raw_groups)


def _response_agent_version_id(response_data: dict[str, Any]) -> str:
    agent_version_id = str(response_data.get("agentVersionId", "")).strip()
    if not agent_version_id:
        raise ValueError("platform response is missing agentVersionId")
    return agent_version_id


def normalize_edit_link_response(
    api_action: str,
    request_body: dict,
    response_data: dict,
    *,
    base_url: str | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    _reject_null_string_fields(response_data, _EDIT_LINK_NULL_STRING_FIELDS, label="edit-link response")
    result = dict(response_data)
    _response_agent_version_id(response_data)
    if not str(result.get("agentId", "")).strip():
        result["agentId"] = str(agent_id or "").strip()
    result["api_action"] = api_action
    result["request_body"] = request_body
    result["agent_runtime"] = str(response_data.get("agentRuntime", "")).strip()
    result["warnings"] = review_url_warnings(
        str(response_data.get("url", "")).strip(),
        base_url=base_url,
    )
    return result


def attach_platform_status(
    response: dict[str, Any],
    data: dict[str, Any],
    *,
    workflow_status: str | None = None,
) -> dict[str, Any]:
    enriched = dict(response)
    if "status" in data:
        enriched["platform_raw_status"] = data.get("status")
    if workflow_status:
        enriched["status"] = workflow_status
    return enriched


def normalize_latest_version_response(agent_id: str, data: dict[str, Any]) -> dict[str, Any]:
    request_body = {"agentId": str(agent_id or "").strip()}
    if not request_body["agentId"]:
        raise ValueError("agent_id must not be empty")
    raw_response = dict(data)
    _reject_null_string_fields(data, _LATEST_VERSION_NULL_STRING_FIELDS, label="latest-version response")
    workflow_info = _parse_json_object(data.get("workflowInfo"), label="workflowInfo")
    selection_groups = strip_default_selection_fields(
        _normalize_selection_groups_from_workflow_info(workflow_info)
    )
    normalized_workflow_info = {
        "selection_groups": selection_groups,
    }
    workflow_description = workflow_info.get("description")
    if isinstance(workflow_description, str) and workflow_description.strip():
        normalized_workflow_info["description"] = workflow_description.strip()
    required_credentials_payload = _parse_json_object(
        data.get("requiredCredentials"),
        label="requiredCredentials",
    )
    _response_agent_version_id(data)

    result = {
        key: raw_response[key]
        for key in _LATEST_VERSION_STABLE_FIELDS
        if key in raw_response
    }
    if not str(result.get("agentId", "")).strip():
        result["agentId"] = request_body["agentId"]
    result["workflow_info"] = normalized_workflow_info
    result["api_action"] = "get_latest_version"
    result["request_body"] = request_body
    result["_raw"] = raw_response
    result["agent_runtime"] = str(data.get("agentRuntime", "")).strip()
    result["env_id"] = env_id_from_agent_runtime(result["agent_runtime"])
    result["agent_version_id"] = str(data.get("agentVersionId", "")).strip()
    result["is_confirmed_skills"] = data.get("isConfirmedSkills")
    result["is_confirmed_config_keys"] = data.get("isConfirmedConfigKeys")
    result["selection_groups"] = selection_groups
    result["required_credentials_payload"] = required_credentials_payload
    result["warnings"] = []
    return result


__all__ = [
    "attach_platform_status",
    "normalize_edit_link_response",
    "normalize_latest_version_response",
]
