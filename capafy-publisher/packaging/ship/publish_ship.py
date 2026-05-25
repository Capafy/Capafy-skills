from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from packaging._shared.common.cli import build_publish_error, emit_json
from packaging._shared.common.constants import (
    DEFAULT_BUNDLE_PATH,
    DEFAULT_STAGING_PATH,
    DEVELOPER_WORK_DIR_PATH,
)
from packaging._shared.common.fs import cleanup_bundle_file, cleanup_staging_root
from packaging._shared.contracts.publish_work_state import (
    STAGE_SHIPPED,
    cleanup_shipped_publish_intermediates,
    write_publish_work_state_manifest,
)
from packaging._shared.contracts.reviewed_scan import credential_counts
from packaging._shared.platform import get_latest_version
from packaging._shared.platform.runtime_mapping import parse_latest_version
from packaging.ship.artifacts.package_pipeline import run_artifact_package
from packaging.ship.artifacts.validate_runtime import run_artifact_validate
from packaging.ship.cloud_hosted.package import require_cloud_hosted_url_proxy
from packaging.ship.cloud_hosted.readback_safety import find_plaintext_required_credentials
from packaging.ship.cloud_hosted.ship_prune import ShipPruneResult, prune_cloud_hosted_reviewed_scan
from packaging.ship.shipping.preflight import ShipContext, prepare_ship_context
from packaging.ship.shipping.upload import publish_upload_and_report


def _build_ship_error(
    ctx: ShipContext,
    *,
    agent_id: str,
    error: str,
    failed_step: str,
    blocking_category: str,
    developer_next_steps: Optional[list[str]] = None,
    **extra: Any,
) -> dict[str, Any]:
    payload = build_publish_error(
        error=error,
        failed_step=failed_step,
        blocking_category=blocking_category,
        developer_next_steps=developer_next_steps,
        agent_id=agent_id,
        agent_version_id=ctx.agent_version_id,
        env_id=ctx.env_id,
        agent_type=ctx.agent_type,
        reviewed_scan_path=ctx.reviewed_scan_path,
        credential_counts=credential_counts(ctx.reviewed_scan),
        **extra,
    )
    return payload


def run_publish_ship(
    *,
    agent_id: str,
    developer_work_dir_path: Path = DEVELOPER_WORK_DIR_PATH,
    default_staging_path: str = DEFAULT_STAGING_PATH,
    default_bundle_path: str = DEFAULT_BUNDLE_PATH,
) -> tuple[dict[str, Any], int]:
    latest = get_latest_version(agent_id)
    context_or_error, context_code = prepare_ship_context(
        agent_id=agent_id,
        latest=latest,
        developer_work_dir_path=developer_work_dir_path,
        default_staging_path=default_staging_path,
    )
    if context_code != 0:
        return context_or_error, context_code
    if not isinstance(context_or_error, ShipContext):
        return build_publish_error(
            error="prepare_ship_context returned an invalid success payload",
            failed_step="prepare_ship_context",
            blocking_category="invalid_ship_context",
            agent_id=agent_id,
        ), 1

    ctx = context_or_error
    bundle_path = default_bundle_path

    if ctx.agent_type == "run_online":
        latest_state = parse_latest_version(latest)
        readback_findings = find_plaintext_required_credentials(latest_state.required_credentials_payload)
        if readback_findings:
            return _build_ship_error(
                ctx,
                agent_id=agent_id,
                error="Platform requiredCredentials readback contains plaintext managed credential values.",
                failed_step="platform_required_credentials_readback",
                blocking_category="plaintext_platform_required_credentials_readback",
                developer_next_steps=[
                    "Confirm the platform requiredCredentials readback does not expose plaintext key/token/secret/password values, then rerun `publish-ship`.",
                ],
                next_step="confirm_platform_required_credentials_readback",
                platform_readback_findings=readback_findings,
            ), 1
        prune_result, prune_code = prune_cloud_hosted_reviewed_scan(
            env_id=ctx.env_id,
            agent_type=ctx.agent_type,
            reviewed_scan=ctx.reviewed_scan,
            staging_root=ctx.staging_root,
            required_credentials_payload=latest_state.required_credentials_payload,
            developer_work_dir_path=developer_work_dir_path,
        )
        if prune_code != 0:
            return prune_result, prune_code
        if not isinstance(prune_result, ShipPruneResult):
            return _build_ship_error(
                ctx,
                agent_id=agent_id,
                error="ship-prune returned an invalid success payload",
                failed_step="ship_prune",
                blocking_category="invalid_prune_result",
            ), 1
        try:
            require_cloud_hosted_url_proxy(prune_result.effective_scan)
        except ValueError as exc:
            return _build_ship_error(
                ctx,
                agent_id=agent_id,
                error=str(exc),
                failed_step="cloud_hosted_url_proxy_gate",
                blocking_category="missing_required_url_proxy",
                developer_next_steps=[
                    "Re-run publish-configure with at least one configured LLM provider, or re-confirm at least one provider on the platform page.",
                ],
            ), 1
        effective_scan_payload = prune_result.effective_scan.to_scan_groups_dict()
    else:
        effective_scan_payload = ctx.reviewed_scan

    try:
        validate_exit, validate_payload = run_artifact_validate(
            staging_path=ctx.staging_root,
            env_id=ctx.env_id,
            reviewed_scan=effective_scan_payload,
            agent_type=ctx.agent_type,
        )
    except (OSError, ValueError) as exc:
        return _build_ship_error(
            ctx,
            agent_id=agent_id,
            error=f"validate failed: {exc}",
            failed_step="validate_runtime",
            blocking_category="validate_runtime_failed",
        ), 1

    credential_totals = credential_counts(ctx.reviewed_scan)

    if validate_exit != 0 or not validate_payload.get("ok"):
        developer_next_steps = validate_payload.get("developer_next_steps")
        if not isinstance(developer_next_steps, list) or not developer_next_steps:
            developer_next_steps = ["Fix the validate-runtime failures, then rerun `publish-ship`."]
        return _build_ship_error(
            ctx,
            agent_id=agent_id,
            error="validate-runtime failed",
            failed_step="validate_runtime",
            blocking_category="validate_runtime_failed",
            developer_next_steps=developer_next_steps,
        ), 1

    try:
        run_artifact_package(
            staging_root=ctx.staging_root,
            reviewed_scan=effective_scan_payload,
            bundle_path=bundle_path,
            agent_type=ctx.agent_type,
        )
    except (OSError, ValueError) as exc:
        return _build_ship_error(
            ctx,
            agent_id=agent_id,
            error=f"package failed: {exc}",
            failed_step="package",
            blocking_category="package_failed",
        ), 1

    upload_result = publish_upload_and_report(
        agent_id,
        ctx.agent_version_id,
        bundle_path,
        staging_root=ctx.staging_root,
        cleanup=False,
        latest_version=latest,
    )

    upload_artifacts = upload_result.get("artifacts") or {}
    cleanup_summary: dict[str, object] = {}
    package_url = upload_artifacts.get("package_url", "")
    review_url = upload_artifacts.get("review_url", "")

    if upload_result.get("stopped"):
        developer_next_steps = upload_result.get("developer_next_steps")
        if not isinstance(developer_next_steps, list) or not developer_next_steps:
            next_step = str(upload_result.get("next_step", "")).strip()
            developer_next_steps = [next_step] if next_step else ["Resolve the upload/report stop condition, then rerun `publish-ship`."]
        return _build_ship_error(
            ctx,
            agent_id=agent_id,
            error=str(upload_result.get("stop_reason", "")).strip() or "upload/report stopped",
            failed_step="upload_and_report",
            blocking_category="upload_and_report_stopped",
            developer_next_steps=developer_next_steps,
            stop_reason=str(upload_result.get("stop_reason", "")).strip(),
            package_url=package_url,
            review_url=review_url,
            cleanup_summary=cleanup_summary,
        ), 1

    if not str(review_url or "").strip():
        return _build_ship_error(
            ctx,
            agent_id=agent_id,
            error="platform-report-package did not return a review URL",
            failed_step="upload_and_report",
            blocking_category="missing_report_package_review_url",
            developer_next_steps=[
                "Retry publish-ship after confirming platform-report-package returns a review URL.",
            ],
            next_step="retry_platform_report_package",
            package_url=package_url,
            cleanup_summary=cleanup_summary,
        ), 1

    cleanup_summary.update(cleanup_bundle_file(bundle_path))
    cleanup_summary.update(cleanup_staging_root(ctx.staging_root))
    cleanup_summary.update(cleanup_shipped_publish_intermediates(developer_work_dir_path))

    extra = dict(ctx.manifest.extra or {})
    extra["staging_path"] = ctx.review_staging_root
    extra["reviewed_scan_path"] = ctx.reviewed_scan_path
    extra["bundle_path"] = bundle_path
    extra["package_url"] = package_url
    extra["cleanup_summary"] = cleanup_summary
    write_publish_work_state_manifest(
        developer_work_dir_path,
        agent_id=agent_id,
        agent_version_id=str(ctx.agent_version_id or "").strip(),
        env_id=ctx.env_id,
        agent_type=ctx.agent_type,
        stage=STAGE_SHIPPED,
        review_url=review_url or None,
        extra=extra,
    )

    return {
        "status": "shipped",
        "agent_id": agent_id,
        "agent_version_id": ctx.agent_version_id,
        "env_id": ctx.env_id,
        "agent_type": ctx.agent_type,
        "reviewed_scan_path": ctx.reviewed_scan_path,
        "credential_counts": credential_totals,
        "bundle_file": bundle_path,
        "staging_root": ctx.review_staging_root,
        "cleanup_summary": cleanup_summary,
        "package_url": package_url,
        "review_url": review_url,
    }, 0


def publish_ship(
    *,
    agent_id: str,
) -> int:
    payload, code = run_publish_ship(
        agent_id=agent_id,
        developer_work_dir_path=DEVELOPER_WORK_DIR_PATH,
        default_staging_path=DEFAULT_STAGING_PATH,
        default_bundle_path=DEFAULT_BUNDLE_PATH,
    )
    emit_json(payload)
    return code


__all__ = [
    "publish_ship",
    "run_publish_ship",
]
