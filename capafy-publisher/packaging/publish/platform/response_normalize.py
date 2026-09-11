from __future__ import annotations

from typing import Any, Optional



_EDIT_LINK_NULL_STRING_FIELDS = (
    "agentVersionId",
    "agentRuntime",
    "url",
)


def _reject_null_string_fields(data: dict[str, Any], fields: tuple[str, ...], *, label: str) -> None:
    for field in fields:
        if field in data and data.get(field) is None:
            raise ValueError(f"platform returned invalid {label}: field {field} must be a string, not null")


def _response_agent_version_id(response_data: dict[str, Any]) -> str:
    agent_version_id = str(response_data.get("agentVersionId", "")).strip()
    if not agent_version_id:
        raise ValueError("platform response is missing agentVersionId")
    return agent_version_id


def normalize_edit_link_response(
    response_data: dict,
    *,
    agent_id: Optional[str] = None,
) -> dict[str, Any]:
    _reject_null_string_fields(response_data, _EDIT_LINK_NULL_STRING_FIELDS, label="edit-link response")
    result = {
        "agentId": str(response_data.get("agentId", "") or agent_id or "").strip(),
        "agentVersionId": _response_agent_version_id(response_data),
        "agentPackageId": response_data.get("agentPackageId"),
        "agentRuntime": str(response_data.get("agentRuntime", "")).strip(),
        "url": str(response_data.get("url", "")).strip(),
    }
    return result


def attach_platform_status(
    response: dict[str, Any],
    data: dict[str, Any],
    *,
    workflow_status: Optional[str] = None,
) -> dict[str, Any]:
    enriched = dict(response)
    if "status" in data:
        enriched["platform_raw_status"] = data.get("status")
    if workflow_status:
        enriched["status"] = workflow_status
    return enriched


__all__ = [
    "attach_platform_status",
    "normalize_edit_link_response",
]
