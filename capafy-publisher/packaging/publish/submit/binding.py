from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Union

from packaging.common.constants import DEFAULT_STAGING_PATH
from packaging.common.cli import build_publish_error
from packaging.publish.domain.publish_work_state import (
    PublishWorkStateManifestError,
    PublishWorkState,
    STAGE_SECURITY_REVIEW_REQUIRED,
    STAGE_PACKAGE_UPLOADED,
    require_publish_work_state,
)
from packaging.publish.platform.runtime_mapping import LatestVersion, PACKAGE_REPORT_ALLOWED_STATUSES, skill_selection_gate
from packaging.publish.reviewed_scan import (
    compute_scan_digest,
    compute_staging_digest,
    is_reviewed_scan_payload,
    load_reviewed_scan_path,
    read_reviewed_scan_file,
    reviewed_scan_context_diagnostics,
    reviewed_scan_matches_context,
)
from packaging.publish.domain.source_snapshot import compute_publish_source_snapshot_digest


@dataclass(frozen=True)
class UploadContext:
    agent_version_id: str
    env_id: str
    agent_type: str
    manifest: PublishWorkState
    reviewed_scan: dict[str, Any]
    reviewed_scan_path: str
    staging_root: str


def prepare_upload_context(
    *,
    agent_id: str,
    latest: LatestVersion,
    developer_work_dir_path: Path,
    default_staging_path: str = DEFAULT_STAGING_PATH,
) -> tuple[Union[UploadContext, dict[str, Any]], int]:
    env_id = latest.env_id
    agent_type = latest.agent_type
    expected_stage = STAGE_SECURITY_REVIEW_REQUIRED

    if latest.status not in PACKAGE_REPORT_ALLOWED_STATUSES:
        return build_publish_error(
            error="Platform version status does not allow package submission",
            failed_step="check_platform_version_status",
            blocking_category="package_report_status_not_allowed",
            developer_next_steps=[
                "Wait until the platform version returns to editable status 0 or 2, then rerun `publish-submit`.",
            ],
            next_step="wait_for_editable_platform_status_then_retry",
            agent_id=agent_id,
            status=latest.status,
        ), 1

    selection_gate = skill_selection_gate(latest)
    if selection_gate == "not_confirmed":
        return build_publish_error(
            error="First webpage confirm not completed",
            failed_step="confirm_skills",
            blocking_category="skills_not_confirmed_on_platform",
            developer_next_steps=[
                "Complete the first webpage confirmation, then rerun `publish-submit`.",
            ],
            next_step="complete_skill_confirmation_then_retry",
            agent_id=agent_id,
        ), 1
    if selection_gate == "empty":
        return build_publish_error(
            error="Platform skill confirmation contains no selected skills",
            failed_step="confirm_skills",
            blocking_category="skills_empty_after_platform_confirmation",
            developer_next_steps=[
                "Select at least one Skill on the platform, then rerun `publish-submit`.",
            ],
            next_step="select_skill_then_retry_publish_submit",
            agent_id=agent_id,
        ), 1

    agent_version_id = latest.agent_version_id
    try:
        manifest = require_publish_work_state(developer_work_dir_path)
    except PublishWorkStateManifestError as exc:
        return build_publish_error(
            error=str(exc),
            failed_step="load_publish_work_state_manifest",
            blocking_category="invalid_publish_work_state_manifest",
            developer_next_steps=[
                "Fix or remove the invalid local publish work-state manifest, then rerun `publish-submit`.",
            ],
            next_step="fix_or_remove_invalid_publish_work_state_manifest",
        ), 1

    if manifest is None:
        return build_publish_error(
            error="publish-submit requires local publish work-state from publish-submit",
            failed_step="load_publish_work_state_manifest",
            blocking_category="missing_publish_work_state_manifest",
            developer_next_steps=[
                "Run `publish-submit` to build staging and complete review/config gates, then retry `publish-submit`.",
            ],
            next_step="rerun_publish_submit",
        ), 1

    if manifest.agent_id != str(agent_id or "").strip():
        return build_publish_error(
            error="agent_id does not match local publish work-state",
            failed_step="check_prerequisite_stage",
            blocking_category="agent_id_mismatch",
            developer_next_steps=[
                "Use the agent_id from the active local publish work-state, or restart the publish flow.",
            ],
            next_step="use_matching_agent_id_or_restart_publish_flow",
        ), 1

    prepared_context = {
        "agent_version_id": manifest.agent_version_id,
        "env_id": manifest.env_id,
        "agent_type": manifest.agent_type,
    }
    platform_context = {
        "agent_version_id": agent_version_id,
        "env_id": env_id,
        "agent_type": agent_type,
    }
    if prepared_context != platform_context:
        return build_publish_error(
            error="platform publish context no longer matches the local prepared state",
            failed_step="check_prepared_platform_context",
            blocking_category="stale_prepared_platform_context",
            developer_next_steps=[
                "Rerun `publish-submit --action prepare` for the platform's current version, runtime, and mode before uploading.",
            ],
            next_step="rerun_publish_submit_prepare",
            agent_id=agent_id,
            prepared_context=prepared_context,
            platform_context=platform_context,
        ), 1

    if manifest.current_stage == STAGE_PACKAGE_UPLOADED:
        return build_publish_error(
            error="publish-submit has already uploaded the package for this local publish work-state",
            failed_step="check_prerequisite_stage",
            blocking_category="already_package_uploaded",
            developer_next_steps=[
                "Do not rerun publish-submit for this local draft.",
                "Use `publish-refresh-url --agent-id <agent_id> --step publish` for a fresh final confirmation link, or `publish-remote-status --agent-id <agent_id>` to inspect platform state.",
            ],
            next_step="refresh_final_review_url_or_check_remote_status",
            agent_id=agent_id,
            agent_version_id=manifest.agent_version_id,
            env_id=manifest.env_id,
            agent_type=manifest.agent_type,
            review_url=manifest.pending_review_url or "",
            package_url=manifest.extra_value("package_url"),
        ), 1

    expected_source_digest = manifest.extra_value("source_snapshot_digest")
    if expected_source_digest:
        source_snapshot_roots = manifest.extra.get("source_snapshot_roots")
        if not isinstance(source_snapshot_roots, list):
            return build_publish_error(
                error="prepared publish state is missing source snapshot roots",
                failed_step="check_source_snapshot_digest",
                blocking_category="invalid_publish_source_snapshot",
                developer_next_steps=["Rerun `publish-submit --action prepare`, then retry `publish-submit --action continue_upload`."],
                next_step="rerun_publish_submit_prepare",
            ), 1
        try:
            current_source_digest = compute_publish_source_snapshot_digest(
                source_roots=source_snapshot_roots,
            )
        except ValueError as exc:
            return build_publish_error(
                error=str(exc),
                failed_step="check_source_snapshot_digest",
                blocking_category="invalid_publish_source_snapshot",
                developer_next_steps=["Rerun `publish-submit --action prepare`, then retry `publish-submit --action continue_upload`."],
                next_step="rerun_publish_submit_prepare",
            ), 1
        if current_source_digest != expected_source_digest:
            return build_publish_error(
                error="publish source inputs no longer match the state prepared by publish-submit",
                failed_step="check_source_snapshot_digest",
                blocking_category="stale_publish_source",
                developer_next_steps=["Rerun `publish-submit --action prepare`, then retry `publish-submit --action continue_upload`."],
                next_step="rerun_publish_submit_prepare",
                expected_source_snapshot_digest=expected_source_digest,
                current_source_snapshot_digest=current_source_digest,
            ), 1

    if manifest.current_stage != expected_stage:
        return build_publish_error(
            error=f"publish-submit for {agent_type} requires {expected_stage} stage",
            failed_step="check_prerequisite_stage",
            blocking_category="missing_prerequisite_stage",
            developer_next_steps=[
                "Run `publish-submit` and complete any required review/config/disposition gates, then retry `publish-submit`.",
            ],
            next_step="rerun_publish_submit",
        ), 1

    staging_root = manifest.staging_path or default_staging_path
    if not Path(staging_root).is_dir():
        return build_publish_error(
            error=f"publish-submit for {agent_type} requires the review staging directory from publish-submit",
            failed_step="check_review_staging",
            blocking_category="missing_review_staging",
            developer_next_steps=[
                "Rerun `publish-submit` to rebuild review staging and complete any required gates.",
            ],
            next_step="rerun_publish_submit",
        ), 1

    current_staging_digest = compute_staging_digest(staging_root)
    if agent_type == "run_online":
        expected_staging_digest = manifest.extra_value("staging_digest")
        if not expected_staging_digest or current_staging_digest != expected_staging_digest:
            return build_publish_error(
                error="run_online staging no longer matches the state prepared by publish-submit",
                failed_step="check_review_staging_digest",
                blocking_category="stale_review_staging",
                developer_next_steps=[
                    "Rerun `publish-submit` for the same agent_id, then retry `publish-submit`.",
                ],
                next_step="rerun_publish_submit",
                agent_id=agent_id,
                agent_version_id=agent_version_id,
                env_id=env_id,
                agent_type=agent_type,
                staging_path=str(staging_root),
                expected_staging_digest=expected_staging_digest,
                current_staging_digest=current_staging_digest,
            ), 1
    reviewed_scan_path = manifest.extra_value("reviewed_scan_path") or load_reviewed_scan_path(
        developer_work_dir_path=developer_work_dir_path
    )
    reviewed_scan = read_reviewed_scan_file(reviewed_scan_path)
    if not is_reviewed_scan_payload(reviewed_scan):
        return build_publish_error(
            error=f"publish-submit for {agent_type} requires reviewed-scan.json from publish-submit",
            failed_step="load_reviewed_scan",
            blocking_category="missing_reviewed_scan",
            developer_next_steps=[
                "Run `publish-submit` to rebuild staging scan state before publishing.",
            ],
            next_step="rerun_publish_submit",
        ), 1
    expected_reviewed_scan_digest = manifest.extra_value("reviewed_scan_digest")
    current_reviewed_scan_digest = compute_scan_digest(reviewed_scan)
    if not expected_reviewed_scan_digest or current_reviewed_scan_digest != expected_reviewed_scan_digest:
        return build_publish_error(
            error="reviewed-scan.json content no longer matches publish-submit state",
            failed_step="check_reviewed_scan_digest",
            blocking_category="stale_reviewed_scan",
            developer_next_steps=[
                "Rerun `publish-submit --action prepare` for the same agent_id, then retry upload.",
            ],
            next_step="rerun_publish_submit",
            agent_id=agent_id,
            agent_version_id=agent_version_id,
            env_id=env_id,
            agent_type=agent_type,
            reviewed_scan_path=str(reviewed_scan_path),
            expected_reviewed_scan_digest=expected_reviewed_scan_digest,
            current_reviewed_scan_digest=current_reviewed_scan_digest,
        ), 1
    review_binding = {
        "staging_digest": current_staging_digest,
        "env_id": env_id,
        "agent_type": agent_type,
    }
    if not reviewed_scan_matches_context(
        reviewed_scan,
        review_binding=review_binding,
    ):
        reviewed_scan_context = reviewed_scan_context_diagnostics(
            reviewed_scan,
            review_binding=review_binding,
        )
        reviewed_scan_context["staging_path"] = str(staging_root)
        reviewed_scan_context["reviewed_scan_path"] = str(reviewed_scan_path)
        return build_publish_error(
            error=f"reviewed-scan.json no longer matches the prepared {agent_type} review staging",
            failed_step="check_reviewed_scan_context",
            blocking_category="stale_reviewed_scan",
            developer_next_steps=[
                "Rerun `publish-submit --action prepare` for the same agent_id and complete any local security decisions.",
            ],
            next_step="rerun_publish_submit",
            agent_id=agent_id,
            agent_version_id=agent_version_id,
            env_id=env_id,
            agent_type=agent_type,
            reviewed_scan_context=reviewed_scan_context,
        ), 1

    return UploadContext(
        agent_version_id=agent_version_id,
        env_id=env_id,
        agent_type=agent_type,
        manifest=manifest,
        reviewed_scan=reviewed_scan,
        reviewed_scan_path=reviewed_scan_path,
        staging_root=staging_root,
    ), 0


__all__ = ["UploadContext", "prepare_upload_context"]
