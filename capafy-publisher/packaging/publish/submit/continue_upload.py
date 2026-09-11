from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from packaging.common.cli import build_publish_error, build_success
from packaging.common.constants import (
    DEFAULT_BUNDLE_PATH,
    DEFAULT_STAGING_PATH,
    DEVELOPER_WORK_DIR_PATH,
)
from packaging.common.fs import cleanup_bundle_file, cleanup_staging_root
from packaging.publish.domain.publish_work_state import (
    STAGE_PACKAGE_UPLOADED,
    cleanup_package_intermediates,
    write_publish_work_state_manifest,
)
from packaging.publish.reviewed_scan import credential_counts
from packaging.publish.platform import get_latest_version
from packaging.publish.artifacts.package import run_artifact_package
from packaging.publish.artifacts.validate_runtime import run_artifact_validate
from packaging.publish.submit.binding import UploadContext, prepare_upload_context
from packaging.publish.platform.required_credentials import build_required_credentials
from packaging.publish.platform.upload import publish_upload_and_submit


def _build_upload_error(
    ctx: UploadContext,
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
        **({"reviewed_scan_path": ctx.reviewed_scan_path} if ctx.reviewed_scan_path else {}),
        **(
            {"credential_counts": credential_counts(ctx.reviewed_scan)}
            if isinstance(ctx.reviewed_scan, dict)
            else {}
        ),
        **extra,
    )
    return payload


def run_continue_upload(
    *,
    agent_id: str,
    developer_work_dir_path: Path = DEVELOPER_WORK_DIR_PATH,
    default_staging_path: str = DEFAULT_STAGING_PATH,
    default_bundle_path: str = DEFAULT_BUNDLE_PATH,
) -> tuple[dict[str, Any], int]:
    latest = get_latest_version(agent_id)
    context_or_error, context_code = prepare_upload_context(
        agent_id=agent_id,
        latest=latest,
        developer_work_dir_path=developer_work_dir_path,
        default_staging_path=default_staging_path,
    )
    if context_code != 0:
        return context_or_error, context_code
    ctx = context_or_error
    bundle_path = default_bundle_path

    try:
        validate_payload = run_artifact_validate(
            staging_path=ctx.staging_root,
            env_id=ctx.env_id,
            reviewed_scan=ctx.reviewed_scan,
            agent_type=ctx.agent_type,
        )
    except (OSError, ValueError) as exc:
        return _build_upload_error(
            ctx,
            agent_id=agent_id,
            error=f"validate failed: {exc}",
            failed_step="validate_runtime",
            blocking_category="validate_runtime_failed",
        ), 1

    if not validate_payload.get("ok"):
        developer_next_steps = validate_payload.get("developer_next_steps")
        if not isinstance(developer_next_steps, list) or not developer_next_steps:
            developer_next_steps = ["Fix the validate-runtime failures, then rerun `publish-submit`."]
        return _build_upload_error(
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
            reviewed_scan=ctx.reviewed_scan,
            bundle_path=bundle_path,
            agent_type=ctx.agent_type,
        )
    except (OSError, ValueError) as exc:
        return _build_upload_error(
            ctx,
            agent_id=agent_id,
            error=f"package failed: {exc}",
            failed_step="package",
            blocking_category="package_failed",
        ), 1

    required_credentials = None
    if ctx.agent_type == "run_online":
        try:
            required_credentials = build_required_credentials(
                ctx.reviewed_scan,
                environment_variables=(ctx.manifest.extra or {}).get("environment_variables"),
                env_id=ctx.env_id,
            )
        except ValueError as exc:
            return _build_upload_error(
                ctx,
                agent_id=agent_id,
                error=f"required credentials failed: {exc}",
                failed_step="build_required_credentials",
                blocking_category="invalid_required_credentials",
                developer_next_steps=[
                    "Rerun `publish-submit --action prepare` to rebuild the reviewed credential configuration.",
                ],
            ), 1

    upload_result = publish_upload_and_submit(
        agent_id,
        ctx.agent_version_id,
        bundle_path,
        biz_type=ctx.agent_type,
        required_credentials=required_credentials,
    )

    upload_artifacts = upload_result.get("artifacts") or {}
    package_url = upload_result.get("package_url") or upload_artifacts.get("package_url", "")
    review_url = upload_result.get("review_url") or upload_artifacts.get("review_url", "")

    if upload_result.get("stopped"):
        developer_next_steps = upload_result.get("developer_next_steps")
        if not isinstance(developer_next_steps, list) or not developer_next_steps:
            next_step = str(upload_result.get("next_step", "")).strip()
            developer_next_steps = [next_step] if next_step else ["Resolve the upload/submit stop condition, then rerun `publish-submit`."]
        return _build_upload_error(
            ctx,
            agent_id=agent_id,
            error=str(upload_result.get("stop_reason", "")).strip() or "upload/submit stopped",
            failed_step="upload_and_submit",
            blocking_category="upload_and_submit_stopped",
            developer_next_steps=developer_next_steps,
            stop_reason=str(upload_result.get("stop_reason", "")).strip(),
            package_url=package_url,
            review_url=review_url,
        ), 1

    extra = dict(ctx.manifest.extra or {})
    extra.pop("environment_variables", None)
    extra["staging_path"] = ctx.staging_root
    if ctx.reviewed_scan_path:
        extra["reviewed_scan_path"] = ctx.reviewed_scan_path
    else:
        extra.pop("reviewed_scan_path", None)
    extra["bundle_path"] = bundle_path
    extra["package_url"] = package_url
    try:
        write_publish_work_state_manifest(
            developer_work_dir_path,
            agent_id=agent_id,
            agent_version_id=str(ctx.agent_version_id or "").strip(),
            env_id=ctx.env_id,
            agent_type=ctx.agent_type,
            stage=STAGE_PACKAGE_UPLOADED,
            review_url=review_url or None,
            extra=extra,
        )
    except (OSError, ValueError) as exc:
        return _build_upload_error(
            ctx,
            agent_id=agent_id,
            error=f"platform package submit succeeded but package uploaded state could not be persisted: {exc}",
            failed_step="persist_package_uploaded_state",
            blocking_category="persist_package_uploaded_state_failed",
            developer_next_steps=[
                "Open the returned review_url and complete the final confirmation page.",
                "Then use `publish-remote-status --agent-id <agent_id>` to confirm the platform state.",
                "If the platform confirms success, do not rerun `publish-submit`; automatic local reconciliation is unavailable, so keep the local bundle and staging until starting the next explicitly confirmed publish flow.",
            ],
            next_step="open_final_review_url_then_check_remote_status",
            requires_user_confirmation=True,
            automatic_local_reconciliation=False,
            package_url=package_url,
            review_url=review_url,
        ), 1

    cleanup_summary: dict[str, object] = {}
    cleanup_summary.update(cleanup_bundle_file(bundle_path))
    cleanup_summary.update(cleanup_staging_root(ctx.staging_root))
    cleanup_summary.update(cleanup_package_intermediates(developer_work_dir_path))

    cleanup_result = {
        "bundle_removed": bool(cleanup_summary.get("bundle_removed")),
        "staging_removed": bool(cleanup_summary.get("staging_removed")),
        "publish_intermediates_removed_count": len(
            cleanup_summary.get("publish_intermediates_removed", [])
            if isinstance(cleanup_summary.get("publish_intermediates_removed"), list)
            else []
        ),
        "has_cleanup_errors": bool(
            cleanup_summary.get("bundle_error")
            or cleanup_summary.get("staging_error")
            or cleanup_summary.get("publish_intermediates_errors")
        ),
    }
    cleanup_errors: list[dict[str, str]] = []
    for target, error_key, kind_key in (
        ("bundle", "bundle_error", "bundle_error_kind"),
        ("staging", "staging_error", "staging_error_kind"),
    ):
        error = str(cleanup_summary.get(error_key, "") or "").strip()
        if error:
            cleanup_errors.append(
                {
                    "target": target,
                    "error": error,
                    "error_kind": str(cleanup_summary.get(kind_key, "") or "").strip(),
                }
            )
    intermediate_errors = cleanup_summary.get("publish_intermediates_errors")
    if isinstance(intermediate_errors, list) and intermediate_errors:
        cleanup_errors.append(
            {
                "target": "publish_intermediates",
                "error": f"{len(intermediate_errors)} cleanup error(s)",
                "error_kind": "partial_cleanup",
            }
        )
    if cleanup_errors:
        cleanup_result["errors"] = cleanup_errors
    payload = build_success(
        status="package_uploaded",
        agent_id=agent_id,
        agent_version_id=ctx.agent_version_id,
        env_id=ctx.env_id,
        agent_type=ctx.agent_type,
        cleanup=cleanup_result,
        package_url=package_url,
        review_url=review_url,
    )
    return payload, 0


__all__ = ["run_continue_upload"]
