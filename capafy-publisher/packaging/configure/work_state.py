from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from packaging._shared.contracts.publish_work_state import (
    STAGE_BUNDLE_PREPARED,
    STAGE_CONFIG_SUBMITTED,
    PublishWorkState,
    write_publish_work_state_manifest,
)


CONFIGURE_RESET_EXTRA_FIELDS = (
    "bundle_path",
    "package_url",
    "cleanup_summary",
    "configure_redaction_summary",
    "buyout_reviewed_scan_ready",
    "buyout_disposition_status",
)

CLOUD_HOSTED_CONFIGURE_RESET_EXTRA_FIELDS = (
    "download_reviewed_scan_ready",
    "download_disposition_status",
    "disposition_summary",
    "reviewed_scan_digest",
)


def configure_extra_without_ship_outputs(extra: Any) -> dict[str, Any]:
    payload = dict(extra) if isinstance(extra, dict) else {}
    for field in CONFIGURE_RESET_EXTRA_FIELDS:
        payload.pop(field, None)
    return payload


def configure_extra_with_review_artifacts(
    extra: Any,
    *,
    staging_path: str,
    reviewed_scan_path: str,
) -> dict[str, Any]:
    payload = configure_extra_without_ship_outputs(extra)
    payload["staging_path"] = staging_path
    payload["reviewed_scan_path"] = reviewed_scan_path
    return payload


def cloud_hosted_configure_extra_with_review_artifacts(
    extra: Any,
    *,
    staging_path: str,
    reviewed_scan_path: str,
) -> dict[str, Any]:
    payload = configure_extra_with_review_artifacts(
        extra,
        staging_path=staging_path,
        reviewed_scan_path=reviewed_scan_path,
    )
    for field in CLOUD_HOSTED_CONFIGURE_RESET_EXTRA_FIELDS:
        payload.pop(field, None)
    return payload


def write_cloud_hosted_bundle_prepared_manifest(
    work_dir: Path,
    *,
    manifest: PublishWorkState,
    agent_id: str,
    agent_version_id: str,
    env_id: str,
    agent_type: str,
    staging_path: str,
    reviewed_scan_path: str,
) -> Path:
    extra = cloud_hosted_configure_extra_with_review_artifacts(
        manifest.extra,
        staging_path=staging_path,
        reviewed_scan_path=reviewed_scan_path,
    )
    return write_publish_work_state_manifest(
        work_dir,
        agent_id=agent_id,
        agent_version_id=agent_version_id,
        env_id=env_id,
        agent_type=agent_type,
        stage=STAGE_BUNDLE_PREPARED,
        extra=extra,
    )


def write_cloud_hosted_config_submitted_manifest(
    work_dir: Path,
    *,
    manifest: PublishWorkState,
    agent_id: str,
    agent_version_id: str,
    env_id: str,
    agent_type: str,
    review_url: Optional[str],
    reviewed_scan_path: str,
) -> Path:
    extra = dict(manifest.extra) if isinstance(manifest.extra, dict) else {}
    extra["reviewed_scan_path"] = reviewed_scan_path
    return write_publish_work_state_manifest(
        work_dir,
        agent_id=agent_id,
        agent_version_id=agent_version_id,
        env_id=env_id,
        agent_type=agent_type,
        stage=STAGE_CONFIG_SUBMITTED,
        review_url=review_url,
        extra=extra,
    )


def write_buyout_bundle_prepared_manifest(
    work_dir: Path,
    *,
    manifest: PublishWorkState,
    agent_id: str,
    agent_version_id: str,
    env_id: str,
    agent_type: str,
    staging_path: str,
    reviewed_scan_path: str,
    reviewed_scan_digest: str,
    disposition_summary: dict[str, int],
    disposition_status: str,
    redaction_summary: Optional[dict[str, Any]] = None,
) -> Path:
    extra = configure_extra_with_review_artifacts(
        manifest.extra,
        staging_path=staging_path,
        reviewed_scan_path=reviewed_scan_path,
    )
    extra["download_reviewed_scan_ready"] = True
    extra["download_disposition_status"] = disposition_status
    extra["reviewed_scan_digest"] = reviewed_scan_digest
    extra["disposition_summary"] = disposition_summary
    if redaction_summary:
        extra["configure_redaction_summary"] = redaction_summary
    return write_publish_work_state_manifest(
        work_dir,
        agent_id=agent_id,
        agent_version_id=agent_version_id,
        env_id=env_id,
        agent_type=agent_type,
        stage=STAGE_BUNDLE_PREPARED,
        review_url=manifest.pending_review_url,
        extra=extra,
    )


__all__ = [
    "CLOUD_HOSTED_CONFIGURE_RESET_EXTRA_FIELDS",
    "CONFIGURE_RESET_EXTRA_FIELDS",
    "cloud_hosted_configure_extra_with_review_artifacts",
    "configure_extra_with_review_artifacts",
    "configure_extra_without_ship_outputs",
    "write_buyout_bundle_prepared_manifest",
    "write_cloud_hosted_bundle_prepared_manifest",
    "write_cloud_hosted_config_submitted_manifest",
]
