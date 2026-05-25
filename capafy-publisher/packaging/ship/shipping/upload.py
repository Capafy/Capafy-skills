from __future__ import annotations
from typing import Optional

from packaging._shared.common.fs import (
    cleanup_bundle_file,
    cleanup_staging_root,
)
from packaging._shared.common.cli import (
    stopped_publish_payload,
)
from capafy_platform.file_api import upload_package_bundle
from packaging._shared.platform import (
    get_latest_version,
    report_package,
)
from packaging.ship.mode_dispatch import get_ship_mode
from packaging._shared.platform.runtime_mapping import (
    PACKAGE_REPORT_ALLOWED_STATUSES,
    parse_latest_version,
)


def publish_upload_and_report(
    agent_id: str,
    agent_version_id: str,
    bundle_file: str,
    *,
    access_token: Optional[str] = None,
    base_url: Optional[str] = None,
    staging_root: Optional[str] = None,
    cleanup: bool = True,
    package_url: Optional[str] = None,
    latest_version: Optional[dict[str, object]] = None,
) -> dict[str, object]:
    base_artifacts = {
        "agent_id": str(agent_id or "").strip(),
        "agent_version_id": str(agent_version_id or "").strip(),
        "bundle_file": bundle_file,
    }
    if latest_version is None:
        try:
            latest_version = get_latest_version(agent_id, access_token=access_token, base_url=base_url)
        except ValueError as exc:
            return stopped_publish_payload(
                stop_reason="platform_latest_version_failed",
                next_step="retry_platform_latest_version",
                artifacts={
                    **base_artifacts,
                    "package_url": str(package_url or "").strip(),
                },
                developer_next_steps=[str(exc) or "platform-latest-version failed"],
                raw_steps=[],
            )
    raw_steps: list[dict[str, object]] = [
        {
            "step": "platform_latest_version",
            "response": latest_version,
        }
    ]

    missing_requirements: list[str] = []
    latest_state = parse_latest_version(latest_version)
    mode = get_ship_mode(latest_state.agent_type)
    if latest_state.status not in PACKAGE_REPORT_ALLOWED_STATUSES:
        missing_requirements.append("status must be 0 or 2")
    if not latest_state.is_confirmed_skills:
        missing_requirements.append("is_confirmed_skills must be 1")
    if mode.requires_config_keys_gate and not latest_state.is_confirmed_config_keys:
        missing_requirements.append("is_confirmed_config_keys must be 1")

    if missing_requirements:
        return stopped_publish_payload(
            stop_reason="card_not_ready_for_package_report",
            next_step="complete_missing_confirmations_then_retry",
            artifacts=base_artifacts,
            missing_requirements=missing_requirements,
            raw_steps=raw_steps,
        )

    normalized_package_url = str(package_url or "").strip()
    if normalized_package_url:
        upload_payload = {
            "package_url": normalized_package_url,
            "uploaded": False,
            "reused_existing_package_url": True,
        }
    else:
        try:
            upload_payload = upload_package_bundle(
                bundle_file,
                agent_version_id=str(agent_version_id or "").strip(),
                access_token=access_token,
                base_url=base_url,
                biz_type=mode.biz_type,
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

    cleanup_summary: dict[str, object] = {}
    if cleanup:
        cleanup_summary.update(cleanup_bundle_file(bundle_file))
        cleanup_summary.update(cleanup_staging_root(staging_root))

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
        "cleanup_summary": cleanup_summary,
        "raw_steps": raw_steps,
    }


__all__ = ["publish_upload_and_report"]
