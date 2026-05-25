from __future__ import annotations

from typing import Any, Optional

from capafy_platform.api import (
    create_agent,
    create_agent_version,
    get_latest_version_raw,
    report_package_raw,
    save_config_keys_raw,
)
from packaging._shared.platform.agent_request import (
    build_agent_create_request,
    build_agent_version_create_request,
    build_package_report_request,
)
from packaging._shared.platform.config_keys_request import build_config_keys_request
from packaging._shared.platform.response_normalize import (
    attach_platform_status,
    normalize_edit_link_response,
    normalize_latest_version_response,
)


def get_latest_version(agent_id: str, *, access_token: Optional[str] = None, base_url: Optional[str] = None) -> dict[str, Any]:
    normalized_agent_id = str(agent_id or "").strip()
    if not normalized_agent_id:
        raise ValueError("agent_id must not be empty")
    data = get_latest_version_raw(normalized_agent_id, access_token=access_token, base_url=base_url)
    return normalize_latest_version_response(normalized_agent_id, data)


def create_agent_from_draft(
    card_draft: dict,
    *,
    access_token: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict[str, Any]:
    request_body = build_agent_create_request(card_draft)
    data = create_agent(request_body, access_token=access_token, base_url=base_url)
    return normalize_edit_link_response("create_agent", request_body, data, base_url=base_url)


def create_version_from_draft(
    agent_id: str,
    card_draft: dict,
    *,
    access_token: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict[str, Any]:
    request_body = build_agent_version_create_request(agent_id, card_draft)
    data = create_agent_version(request_body, access_token=access_token, base_url=base_url)
    response = normalize_edit_link_response("create_version", request_body, data, base_url=base_url, agent_id=agent_id)
    return attach_platform_status(response, data, workflow_status="pending_skill_confirmation")


def save_config_keys(
    agent_id: str,
    agent_version_id: str,
    reviewed_scan_payload: dict,
    *,
    access_token: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict[str, Any]:
    normalized_agent_id = str(agent_id or "").strip()
    if not normalized_agent_id:
        raise ValueError("agent_id must not be empty")
    request_body = build_config_keys_request(agent_version_id, reviewed_scan_payload)
    data = save_config_keys_raw(
        normalized_agent_id,
        request_body,
        access_token=access_token,
        base_url=base_url,
    )
    response = normalize_edit_link_response(
        "save_config_keys",
        request_body,
        data,
        base_url=base_url,
        agent_id=normalized_agent_id,
    )
    return attach_platform_status(response, data, workflow_status="pending_config_confirmation")


def report_package(
    agent_id: str,
    agent_version_id: str,
    package_url: str,
    *,
    access_token: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict[str, Any]:
    normalized_agent_id = str(agent_id or "").strip()
    if not normalized_agent_id:
        raise ValueError("agent_id must not be empty")
    request_body = build_package_report_request(agent_version_id, package_url)
    data = report_package_raw(
        normalized_agent_id,
        request_body,
        access_token=access_token,
        base_url=base_url,
    )
    response = normalize_edit_link_response(
        "report_package",
        request_body,
        data,
        base_url=base_url,
        agent_id=normalized_agent_id,
    )
    return attach_platform_status(response, data, workflow_status="pending_package_review")


__all__ = [
    "create_agent_from_draft",
    "create_version_from_draft",
    "get_latest_version",
    "report_package",
    "save_config_keys",
]
