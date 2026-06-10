from __future__ import annotations

from typing import Any, Optional

from capafy_platform.api import refresh_draft_url_raw, review_url_warnings
from packaging._shared.common.cli import build_publish_error, build_soft_action, emit_json_result

VALID_REVIEW_URL_STEPS = frozenset({"init", "configure", "ship"})
STEP_PURPOSES = {
    "init": "confirm the file contents to upload",
    "configure": "confirm the keys / environment variables etc. to be hosted",
    "ship": "make the final confirmation and submit for review",
}


def _normalize_step(step: Optional[str]) -> Optional[str]:
    normalized = str(step or "").strip().lower()
    if not normalized:
        return None
    if normalized not in VALID_REVIEW_URL_STEPS:
        raise ValueError("step must be one of init, configure, ship")
    return normalized


def run_publish_refresh_url(*, agent_id: str, step: Optional[str] = None) -> tuple[dict[str, Any], int]:
    normalized_agent_id = str(agent_id or "").strip()
    if not normalized_agent_id:
        return build_publish_error(
            error="agent_id must not be empty",
            failed_step="refresh_review_url",
        ), 1

    try:
        normalized_step = _normalize_step(step)
    except ValueError as exc:
        return build_publish_error(
            error=str(exc),
            failed_step="refresh_review_url",
        ), 1

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
    web_confirmation: dict[str, Any] = {
        "required": True,
    }
    if normalized_step:
        web_confirmation["step"] = normalized_step
        web_confirmation["purpose"] = STEP_PURPOSES[normalized_step]

    return build_soft_action(
        status="review_url_refreshed",
        action_type="creator_web_confirmation",
        next_step="paste_review_url_to_creator",
        developer_next_steps=[
            "Paste review_url verbatim to the creator and wait for the web confirmation to be completed.",
            "After the creator completes the page, reconcile with publish-remote-status or get_latest_version_raw.",
        ],
        status_scope="platform_latest_editable_version",
        agent_id=response_agent_id,
        agent_version_id=str(edit_link.get("agentVersionId", "")).strip(),
        agent_package_id=edit_link.get("agentPackageId"),
        agent_runtime=str(edit_link.get("agentRuntime", "")).strip(),
        step=normalized_step,
        review_url=review_url,
        warnings=review_url_warnings(review_url),
        web_confirmation=web_confirmation,
    ), 0


def publish_refresh_url(*, agent_id: str, step: Optional[str] = None) -> int:
    payload, code = run_publish_refresh_url(agent_id=agent_id, step=step)
    return emit_json_result(payload, code)


__all__ = [
    "publish_refresh_url",
    "run_publish_refresh_url",
]
