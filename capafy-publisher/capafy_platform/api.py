from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlparse

from capafy_platform.http import (
    get_platform_json,
    normalize_platform_base_url,
    post_platform_json,
)


def review_url_warnings(review_url: str, *, base_url: Optional[str] = None) -> list[str]:
    normalized_review_url = str(review_url or "").strip()
    if not normalized_review_url:
        return []
    review_host = str(urlparse(normalized_review_url).hostname or "").strip()
    if not review_host:
        return []
    base_host = str(urlparse(normalize_platform_base_url(base_url)).hostname or "").strip()
    if not base_host:
        return []
    if review_host in {"127.0.0.1", "localhost"} and review_host != base_host:
        return [
            f"review_url points to loopback host {review_host} while base_url host is {base_host}; the returned page may be unreachable from the current host"
        ]
    return []


def get_latest_version_raw(agent_id: str, *, access_token: Optional[str] = None, base_url: Optional[str] = None) -> dict[str, Any]:
    normalized_agent_id = str(agent_id or "").strip()
    if not normalized_agent_id:
        raise ValueError("agent_id must not be empty")
    return get_platform_json(f"/agent/agents/{normalized_agent_id}", access_token=access_token, base_url=base_url, require_auth=True)


def list_agents_raw(*, access_token: Optional[str] = None, base_url: Optional[str] = None) -> dict[str, Any]:
    return get_platform_json("/agent/agents", access_token=access_token, base_url=base_url, require_auth=True)


def get_account_me_raw(*, access_token: Optional[str] = None, base_url: Optional[str] = None) -> dict[str, Any]:
    normalized_access_token = str(access_token or "").strip()
    if not normalized_access_token:
        raise ValueError("access_token must not be empty")
    return get_platform_json(
        "/agent/account",
        access_token=normalized_access_token,
        base_url=base_url,
        require_auth=True,
        unauthorized_message="access_token is invalid or expired",
        allow_raw_dict_without_code=True,
    )


def create_agent(
    request_body: dict[str, Any],
    *,
    access_token: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict[str, Any]:
    if not isinstance(request_body, dict):
        raise ValueError("request_body must be an object")
    return post_platform_json("/agent/agents/addAgent", request_body, access_token=access_token, base_url=base_url, require_auth=True)


def create_agent_version(
    request_body: dict[str, Any],
    *,
    access_token: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict[str, Any]:
    if not isinstance(request_body, dict):
        raise ValueError("request_body must be an object")
    return post_platform_json("/agent/agents/addAgentVersion", request_body, access_token=access_token, base_url=base_url, require_auth=True)


def save_config_keys_raw(
    agent_id: str,
    request_body: dict[str, Any],
    *,
    access_token: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict[str, Any]:
    normalized_agent_id = str(agent_id or "").strip()
    if not normalized_agent_id:
        raise ValueError("agent_id must not be empty")
    if not isinstance(request_body, dict):
        raise ValueError("request_body must be an object")
    return post_platform_json(
        f"/agent/agents/{normalized_agent_id}/credentials", request_body, access_token=access_token, base_url=base_url, require_auth=True
    )


def report_package_raw(
    agent_id: str,
    request_body: dict[str, Any],
    *,
    access_token: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict[str, Any]:
    normalized_agent_id = str(agent_id or "").strip()
    if not normalized_agent_id:
        raise ValueError("agent_id must not be empty")
    if not isinstance(request_body, dict):
        raise ValueError("request_body must be an object")
    return post_platform_json(
        f"/agent/agents/{normalized_agent_id}/uploadPackage", request_body, access_token=access_token, base_url=base_url, require_auth=True
    )


__all__ = [
    "create_agent",
    "create_agent_version",
    "get_account_me_raw",
    "get_latest_version_raw",
    "list_agents_raw",
    "report_package_raw",
    "review_url_warnings",
    "save_config_keys_raw",
]
