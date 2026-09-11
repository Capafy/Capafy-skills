from __future__ import annotations

import json
from typing import Optional

from capafy_platform.file_api import upload_package_bundle
from packaging.publish.platform import submit_package


def _stopped_upload_result(
    *,
    stop_reason: str,
    next_step: str,
    developer_next_steps: list[str],
    package_url: str = "",
) -> dict[str, object]:
    return {
        "ok": False,
        "status": "error",
        "stopped": True,
        "requires_action": False,
        "stop_reason": stop_reason,
        "next_step": next_step,
        "developer_next_steps": developer_next_steps,
        "package_url": package_url,
        "review_url": "",
    }


def publish_upload_and_submit(
    agent_id: str,
    agent_version_id: str,
    bundle_file: str,
    *,
    biz_type: str,
    required_credentials: Optional[str] = None,
    access_token: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict[str, object]:
    normalized_biz_type = str(biz_type or "").strip()
    final_required_credentials = None
    if normalized_biz_type == "run_online":
        if not isinstance(required_credentials, str) or not required_credentials.strip():
            return _stopped_upload_result(
                stop_reason="required_credentials_missing",
                next_step="rerun_publish_submit_prepare",
                developer_next_steps=[
                    "Run Online requires the reviewed credential configuration from the latest prepare step.",
                ],
            )
        final_required_credentials = required_credentials.strip()
        try:
            credentials_payload = json.loads(final_required_credentials)
        except json.JSONDecodeError:
            credentials_payload = None
        if not isinstance(credentials_payload, dict):
            return _stopped_upload_result(
                stop_reason="required_credentials_invalid",
                next_step="rerun_publish_submit_prepare",
                developer_next_steps=[
                    "Run Online requiredCredentials must be a JSON object string produced by prepare.",
                ],
            )
    elif normalized_biz_type == "download" and required_credentials not in (None, ""):
        return _stopped_upload_result(
            stop_reason="download_required_credentials_forbidden",
            next_step="rerun_publish_submit_prepare",
            developer_next_steps=[
                "Download package submission must not include requiredCredentials.",
            ],
        )

    try:
        upload_payload = upload_package_bundle(
            bundle_file,
            agent_version_id=str(agent_version_id or "").strip(),
            access_token=access_token,
            base_url=base_url,
            biz_type=normalized_biz_type,
        )
    except ValueError as exc:
        return _stopped_upload_result(
            stop_reason="platform_upload_package_failed",
            next_step="retry_platform_upload_package",
            developer_next_steps=[str(exc) or "platform-upload-package failed"],
        )

    resolved_package_url = str(upload_payload.get("package_url", "")).strip()
    try:
        submit_payload = submit_package(
            agent_id,
            agent_version_id,
            resolved_package_url,
            required_credentials=final_required_credentials,
            access_token=access_token,
            base_url=base_url,
        )
    except ValueError as exc:
        return _stopped_upload_result(
            stop_reason="platform_submit_package_failed",
            next_step="retry_platform_submit_package",
            developer_next_steps=[str(exc) or "platform-submit-package failed"],
            package_url=resolved_package_url,
        )
    review_url = str(submit_payload.get("url", "")).strip()
    if not review_url:
        return _stopped_upload_result(
            stop_reason="platform_submit_package_missing_review_url",
            next_step="retry_platform_submit_package",
            developer_next_steps=[
                "Retry the final package submit or inspect the platform response; publish-submit can only finish after the merged endpoint returns a review URL.",
            ],
            package_url=resolved_package_url,
        )

    return {
        "ok": True,
        "status": "uploaded_and_submitted",
        "stopped": False,
        "requires_action": False,
        "package_url": resolved_package_url,
        "review_url": review_url,
    }


__all__ = ["publish_upload_and_submit"]
