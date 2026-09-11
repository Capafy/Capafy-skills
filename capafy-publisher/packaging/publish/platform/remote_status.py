from __future__ import annotations

from typing import Any, Optional

from capafy_platform.api import list_agents_raw, refresh_draft_url_raw, review_url_warnings
from packaging.common.cli import build_publish_error, build_soft_action, emit_json_result
from packaging.common.cli import build_success
from packaging.publish.platform.facade import get_latest_version


def _agent_list_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_items = payload.get("list")
    if not isinstance(raw_items, list):
        raw_items = payload.get("records")
    if not isinstance(raw_items, list):
        raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        return []
    items: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "agent_id": str(item.get("agentId", "")).strip(),
                "name": str(item.get("name", "") or "").strip(),
                "description": item.get("desc"),
                "agent_type": str(item.get("agentType", "") or "").strip(),
                "agent_status": str(item.get("agentStatus", "") or "").strip(),
                "latest_agent_version_id": str(item.get("latestAgentVersionId", "") or "").strip(),
                "updated_at": item.get("updatedAt"),
            }
        )
    return items


def run_publish_remote_status(*, agent_id: str) -> tuple[dict[str, Any], int]:
    normalized_agent_id = str(agent_id or "").strip()
    if not normalized_agent_id:
        return build_publish_error(
            error="agent_id must not be empty",
            failed_step="read_remote_status",
        ), 1
    latest_version = get_latest_version(normalized_agent_id)
    response_agent_id = latest_version.agent_id
    if response_agent_id != normalized_agent_id:
        return build_publish_error(
            error="platform latest-version response does not match the requested agent_id",
            failed_step="validate_remote_status_identity",
            blocking_category="remote_agent_id_mismatch",
            developer_next_steps=[
                "Do not trust this response as publish truth; retry the same agent lookup or inspect the platform API routing.",
            ],
            agent_id=normalized_agent_id,
            response_agent_id=response_agent_id,
        ), 1
    public_latest = latest_version.public_payload()
    return build_success(
        status="remote_status",
        status_scope="platform_publish_truth",
        agent_id=normalized_agent_id,
        latest_version=public_latest,
        can_report_published=public_latest["can_report_published"],
        platform_status=public_latest["platform_status"],
        status_complete=public_latest["status_complete"],
    ), 0


VALID_REVIEW_URL_STEPS = frozenset({"init", "publish"})
STEP_PURPOSES = {
    "init": "confirm the file contents to upload",
    "publish": "confirm package configuration and make the final submission",
}


def _normalize_review_url_step(step: Optional[str]) -> Optional[str]:
    normalized = str(step or "").strip().lower()
    if not normalized:
        return None
    if normalized not in VALID_REVIEW_URL_STEPS:
        raise ValueError("step must be one of init, publish")
    return normalized


def run_publish_refresh_url(*, agent_id: str, step: Optional[str] = None) -> tuple[dict[str, Any], int]:
    normalized_agent_id = str(agent_id or "").strip()
    if not normalized_agent_id:
        return build_publish_error(error="agent_id must not be empty", failed_step="refresh_review_url"), 1
    try:
        normalized_step = _normalize_review_url_step(step)
    except ValueError as exc:
        return build_publish_error(error=str(exc), failed_step="refresh_review_url"), 1

    edit_link = refresh_draft_url_raw(normalized_agent_id)
    review_url = str(edit_link.get("url", "")).strip()
    if not review_url:
        return build_publish_error(
            error="platform editLink response is missing url",
            failed_step="refresh_review_url",
            blocking_category="missing_review_url",
            developer_next_steps=[
                "Retry publish-refresh-url after confirming the latest version is still editable on the platform.",
            ],
        ), 1

    response_agent_id = str(edit_link.get("agentId", "") or normalized_agent_id).strip()
    web_confirmation: dict[str, Any] = {"required": True}
    if normalized_step:
        web_confirmation["step"] = normalized_step
        web_confirmation["purpose"] = STEP_PURPOSES[normalized_step]
    warnings = review_url_warnings(review_url)
    return build_soft_action(
        status="review_url_refreshed",
        action_type="creator_web_confirmation",
        next_step="paste_review_url_to_creator",
        developer_next_steps=[
            "Paste review_url verbatim to the creator and wait for the web confirmation to be completed.",
            "After the creator completes the page, reconcile with publish-remote-status.",
        ],
        status_scope="platform_latest_editable_version",
        agent_id=response_agent_id,
        agent_version_id=str(edit_link.get("agentVersionId", "")).strip(),
        review_url=review_url,
        **({"warnings": warnings} if warnings else {}),
        web_confirmation=web_confirmation,
    ), 0


def publish_refresh_url(*, agent_id: str, step: Optional[str] = None) -> int:
    payload, code = run_publish_refresh_url(agent_id=agent_id, step=step)
    return emit_json_result(payload, code)


def run_publish_list() -> tuple[dict[str, Any], int]:
    agents = list_agents_raw()
    return build_success(
        status="agents_list",
        status_scope="platform_account",
        agents=_agent_list_items(agents),
    ), 0


def publish_remote_status(agent_id: str) -> int:
    payload, code = run_publish_remote_status(agent_id=agent_id)
    return emit_json_result(payload, code)


def publish_list() -> int:
    payload, code = run_publish_list()
    return emit_json_result(payload, code)


__all__ = [
    "publish_list",
    "publish_remote_status",
    "run_publish_list",
    "run_publish_remote_status",
]
