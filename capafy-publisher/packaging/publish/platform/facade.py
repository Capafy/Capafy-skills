from __future__ import annotations

from typing import Any, Optional

from capafy_platform.api import (
    create_agent,
    create_agent_version,
    get_latest_version_raw,
    submit_package_credentials_raw,
)
from packaging.publish.platform.agent_request import (
    build_agent_create_request,
    build_agent_version_create_request,
    build_package_submit_request,
)
from packaging.publish.platform.response_normalize import (
    attach_platform_status,
    normalize_edit_link_response,
)
from packaging.publish.platform.runtime_mapping import LatestVersion


def get_latest_version(
    agent_id: str,
    *,
    access_token: Optional[str] = None,
    base_url: Optional[str] = None,
) -> LatestVersion:
    normalized_agent_id = str(agent_id or "").strip()
    if not normalized_agent_id:
        raise ValueError("agent_id must not be empty")
    data = get_latest_version_raw(normalized_agent_id, access_token=access_token, base_url=base_url)
    return LatestVersion.from_response(normalized_agent_id, data)


def create_agent_from_draft(
    card_draft: dict,
    *,
    access_token: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict[str, Any]:
    request_body = build_agent_create_request(card_draft)
    data = create_agent(request_body, access_token=access_token, base_url=base_url)
    return normalize_edit_link_response(data)


def create_version_from_draft(
    agent_id: str,
    card_draft: dict,
    *,
    access_token: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict[str, Any]:
    request_body = build_agent_version_create_request(agent_id, card_draft)
    data = create_agent_version(request_body, access_token=access_token, base_url=base_url)
    response = normalize_edit_link_response(data, agent_id=agent_id)
    return attach_platform_status(response, data, workflow_status="pending_skill_confirmation")


def submit_package(
    agent_id: str,
    agent_version_id: str,
    package_url: str,
    *,
    required_credentials: Optional[str] = None,
    access_token: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict[str, Any]:
    normalized_agent_id = str(agent_id or "").strip()
    if not normalized_agent_id:
        raise ValueError("agent_id must not be empty")
    request_body = build_package_submit_request(
        agent_version_id,
        package_url,
        required_credentials=required_credentials,
    )
    data = submit_package_credentials_raw(
        normalized_agent_id,
        request_body,
        access_token=access_token,
        base_url=base_url,
    )
    if not isinstance(data, dict):
        raise ValueError("merged package submit response must be an object")
    response_agent_id = str(data.get("agentId", "") or "").strip()
    response_version_id = str(data.get("agentVersionId", "") or "").strip()
    response_package_id = str(data.get("agentPackageId", "") or "").strip()
    if response_agent_id != normalized_agent_id:
        raise ValueError("merged package submit response agentId does not match the request")
    if response_version_id != request_body["agentVersionId"]:
        raise ValueError("merged package submit response agentVersionId does not match the request")
    if not response_package_id:
        raise ValueError("merged package submit response agentPackageId must not be empty")
    response = normalize_edit_link_response(data, agent_id=normalized_agent_id)
    return attach_platform_status(response, data, workflow_status="pending_package_review")


__all__ = [
    "create_agent_from_draft",
    "create_version_from_draft",
    "get_latest_version",
    "submit_package",
]
