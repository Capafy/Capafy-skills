from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

from packaging._shared.common.constants import DEFAULT_STAGING_PATH
from packaging._shared.common.cli import build_publish_error
from packaging._shared.contracts.publish_work_state import (
    PublishWorkStateManifestError,
    PublishWorkState,
    STAGE_BUNDLE_PREPARED,
    STAGE_CONFIG_SUBMITTED,
    STAGE_SHIPPED,
    require_publish_work_state,
)
from packaging._shared.reviewed_scan.digest import compute_staging_digest
from packaging._shared.platform.runtime_mapping import PACKAGE_REPORT_ALLOWED_STATUSES, parse_latest_version
from packaging._shared.contracts.reviewed_scan import (
    is_reviewed_scan_payload,
    reviewed_scan_context_diagnostics,
    reviewed_scan_matches_context,
)
from packaging._shared.reviewed_scan.io import (
    load_reviewed_scan_path,
    read_reviewed_scan_file,
)


@dataclass(frozen=True)
class ShipContext:
    agent_version_id: str
    env_id: str
    agent_type: str
    manifest: PublishWorkState
    reviewed_scan: dict[str, Any]
    reviewed_scan_path: str
    staging_root: str
    required_credentials_payload: Optional[dict[str, Any]]


def prepare_ship_context(
    *,
    agent_id: str,
    latest: dict[str, Any],
    developer_work_dir_path: Path,
    default_staging_path: str = DEFAULT_STAGING_PATH,
) -> tuple[Union[ShipContext, dict[str, Any]], int]:
    latest_state = parse_latest_version(latest)
    env_id = latest_state.env_id
    agent_type = latest_state.agent_type
    requires_config_keys_gate = agent_type == "run_online"
    expected_stage = STAGE_CONFIG_SUBMITTED if requires_config_keys_gate else STAGE_BUNDLE_PREPARED

    if latest_state.status not in PACKAGE_REPORT_ALLOWED_STATUSES:
        return build_publish_error(
            error="Platform version status does not allow package report",
            failed_step="check_platform_version_status",
            blocking_category="package_report_status_not_allowed",
            developer_next_steps=[
                "Wait until the platform version returns to editable status 0 or 2, then rerun `publish-ship`.",
            ],
            next_step="wait_for_editable_platform_status_then_retry",
            agent_id=agent_id,
            status=latest_state.status,
        ), 1

    if not latest_state.is_confirmed_skills:
        return build_publish_error(
            error="First webpage confirm not completed",
            failed_step="confirm_skills",
            blocking_category="skills_not_confirmed_on_platform",
            developer_next_steps=[
                "Complete the first webpage confirmation, then rerun `publish-ship`.",
            ],
            next_step="complete_skill_confirmation_then_retry",
            agent_id=agent_id,
        ), 1

    if requires_config_keys_gate and not latest_state.is_confirmed_config_keys:
        return build_publish_error(
            error="Second webpage confirm not completed",
            failed_step="confirm_config_keys",
            blocking_category="config_keys_not_confirmed_on_platform",
            developer_next_steps=[
                "Complete the second webpage confirmation, then rerun `publish-ship`.",
            ],
            next_step="complete_config_confirmation_then_retry",
            agent_id=agent_id,
        ), 1

    agent_version_id = latest_state.agent_version_id
    try:
        manifest = require_publish_work_state(developer_work_dir_path)
    except PublishWorkStateManifestError as exc:
        return build_publish_error(
            error=str(exc),
            failed_step="load_publish_work_state_manifest",
            blocking_category="invalid_publish_work_state_manifest",
            developer_next_steps=[
                "Fix or remove the invalid local publish work-state manifest, then rerun `publish-configure`.",
            ],
            next_step="fix_or_remove_invalid_publish_work_state_manifest",
        ), 1

    if manifest is None:
        return build_publish_error(
            error="publish-ship requires local publish work-state from publish-configure",
            failed_step="load_publish_work_state_manifest",
            blocking_category="missing_publish_work_state_manifest",
            developer_next_steps=[
                "Run `publish-configure` to build staging and complete review/config gates, then retry `publish-ship`.",
            ],
            next_step="rerun_publish_configure",
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

    if manifest.current_stage == STAGE_SHIPPED:
        return build_publish_error(
            error="publish-ship has already uploaded the package for this local publish work-state",
            failed_step="check_prerequisite_stage",
            blocking_category="already_shipped",
            developer_next_steps=[
                "Do not rerun publish-ship for this local draft.",
                "Use `publish-refresh-url --agent-id <agent_id> --step ship` for a fresh final confirmation link, or `publish-remote-status --agent-id <agent_id>` to inspect platform state.",
            ],
            next_step="refresh_final_review_url_or_check_remote_status",
            agent_id=agent_id,
            agent_version_id=manifest.agent_version_id,
            env_id=manifest.env_id,
            agent_type=manifest.agent_type,
            review_url=manifest.pending_review_url or "",
            package_url=manifest.extra_value("package_url"),
        ), 1

    if manifest.current_stage != expected_stage:
        return build_publish_error(
            error=f"publish-ship for {agent_type} requires {expected_stage} stage",
            failed_step="check_prerequisite_stage",
            blocking_category="missing_prerequisite_stage",
            developer_next_steps=[
                "Run `publish-configure` and complete any required review/config/disposition gates, then retry `publish-ship`.",
            ],
            next_step="rerun_publish_configure",
        ), 1

    staging_root = manifest.staging_path or default_staging_path
    reviewed_scan_path = load_reviewed_scan_path(developer_work_dir_path=developer_work_dir_path)
    reviewed_scan = read_reviewed_scan_file(reviewed_scan_path)
    if not Path(staging_root).is_dir():
        return build_publish_error(
            error=f"publish-ship for {agent_type} requires the review staging directory from publish-configure",
            failed_step="check_review_staging",
            blocking_category="missing_review_staging",
            developer_next_steps=[
                "Rerun `publish-configure` to rebuild review staging and complete any required gates.",
            ],
            next_step="rerun_publish_configure",
        ), 1

    if not is_reviewed_scan_payload(reviewed_scan):
        return build_publish_error(
            error=f"publish-ship for {agent_type} requires reviewed-scan.json from publish-configure",
            failed_step="load_reviewed_scan",
            blocking_category="missing_reviewed_scan",
            developer_next_steps=[
                "Run `publish-configure` to rebuild staging scan state before publishing.",
            ],
            next_step="rerun_publish_configure",
        ), 1
    review_binding = {
        "staging_digest": compute_staging_digest(staging_root),
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
                "Rerun `publish-configure` for the same agent_id and complete review/config/disposition gates.",
            ],
            next_step="rerun_publish_configure",
            agent_id=agent_id,
            agent_version_id=agent_version_id,
            env_id=env_id,
            agent_type=agent_type,
            reviewed_scan_context=reviewed_scan_context,
        ), 1

    return ShipContext(
        agent_version_id=agent_version_id,
        env_id=env_id,
        agent_type=agent_type,
        manifest=manifest,
        reviewed_scan=reviewed_scan,
        reviewed_scan_path=reviewed_scan_path,
        staging_root=staging_root,
        required_credentials_payload=latest_state.required_credentials_payload,
    ), 0


__all__ = ["ShipContext", "prepare_ship_context"]
