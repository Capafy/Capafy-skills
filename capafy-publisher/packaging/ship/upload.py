from __future__ import annotations

from typing import Optional

from packaging._shared.common.cli import stopped_publish_payload
from capafy_platform.file_api import upload_package_bundle
from packaging._shared.platform import report_package


def publish_upload_and_report(
    agent_id: str,
    agent_version_id: str,
    bundle_file: str,
    *,
    biz_type: str,
    access_token: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict[str, object]:
    base_artifacts = {
        "agent_id": str(agent_id or "").strip(),
        "agent_version_id": str(agent_version_id or "").strip(),
        "bundle_file": bundle_file,
    }
    raw_steps: list[dict[str, object]] = []

    try:
        upload_payload = upload_package_bundle(
            bundle_file,
            agent_version_id=str(agent_version_id or "").strip(),
            access_token=access_token,
            base_url=base_url,
            biz_type=biz_type,
        )
    except ValueError as exc:
        return stopped_publish_payload(
            stop_reason="platform_upload_package_failed",
            next_step="retry_platform_upload_package",
            artifacts=base_artifacts,
            developer_next_steps=[str(exc) or "platform-upload-package failed"],
            raw_steps=raw_steps,
        )
    raw_steps.append(
        {
            "step": "platform_upload_package",
            "response": upload_payload,
        }
    )

    resolved_package_url = str(upload_payload.get("package_url", "")).strip()
    try:
        report_payload = report_package(
            agent_id,
            agent_version_id,
            resolved_package_url,
            access_token=access_token,
            base_url=base_url,
        )
    except ValueError as exc:
        return stopped_publish_payload(
            stop_reason="platform_report_package_failed",
            next_step="retry_platform_report_package",
            artifacts={
                **base_artifacts,
                "package_url": resolved_package_url,
            },
            developer_next_steps=[str(exc) or "platform-report-package failed"],
            raw_steps=raw_steps,
        )
    raw_steps.append(
        {
            "step": "platform_report_package",
            "response": report_payload,
        }
    )
    review_url = str(report_payload.get("url", "")).strip()
    if not review_url:
        return stopped_publish_payload(
            stop_reason="platform_report_package_missing_review_url",
            next_step="retry_platform_report_package",
            artifacts={
                **base_artifacts,
                "package_url": resolved_package_url,
                "review_url": "",
            },
            developer_next_steps=[
                "Retry platform-report-package or inspect the platform response; publish-ship can only finish after report-package returns a review URL.",
            ],
            raw_steps=raw_steps,
        )

    return {
        "ok": True,
        "stopped": False,
        "stop_reason": "",
        "next_step": "open_final_review_url",
        "requires_user_confirmation": True,
        "artifacts": {
            **base_artifacts,
            "package_url": str(upload_payload.get("package_url", "")).strip(),
            "review_url": review_url,
        },
        "raw_steps": raw_steps,
    }


__all__ = ["publish_upload_and_report"]
