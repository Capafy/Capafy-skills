from __future__ import annotations

from typing import Any, Optional

from packaging.publish.domain.contexts import PrepareContext
from packaging.publish.profiles.download.prepare import load_dispose_overrides_json
from packaging.publish.profiles.mode_dispatch import get_publish_profile
from packaging.publish.security.sensitive.deep_scan_findings import (
    load_deep_scan_findings_file,
)
from packaging.common.cli import build_publish_error
from packaging.publish.platform.runtime_mapping import skill_selection_gate
from packaging.publish.platform import get_latest_version


def run_prepare(
    *,
    agent_id: str,
    manifest: Any,
    dispositions_file: Optional[str],
    deep_scan: bool,
    deep_scan_findings_file: Optional[str],
    environment_selection_file: Optional[str],
) -> tuple[dict[str, Any], int]:
    if manifest.agent_id != str(agent_id or "").strip():
        return build_publish_error(
            error="agent_id does not match local publish work-state",
            failed_step="check_publish_prerequisite",
            blocking_category="agent_id_mismatch",
            next_step="use_matching_agent_id_or_restart_publish_init",
        ), 1
    latest_state = get_latest_version(agent_id)
    selection_gate = skill_selection_gate(latest_state)
    if selection_gate == "not_confirmed":
        return build_publish_error(
            error="skill confirmation not completed",
            failed_step="confirm_skills",
            blocking_category="skills_not_confirmed_on_platform",
            next_step="complete_skill_confirmation_then_retry",
        ), 1
    if selection_gate == "empty":
        return build_publish_error(
            error="platform skill confirmation contains no selected skills",
            failed_step="confirm_skills",
            blocking_category="skills_empty_after_platform_confirmation",
            next_step="select_skill_then_retry_publish_submit",
        ), 1
    agent_type = latest_state.agent_type
    try:
        profile = get_publish_profile(agent_type)
    except ValueError as exc:
        return build_publish_error(
            error=str(exc),
            failed_step="check_agent_type",
            blocking_category="unsupported_agent_type",
            next_step="fix_platform_agent_type_then_retry",
        ), 1
    overrides = load_dispose_overrides_json(dispositions_file) if dispositions_file else {}
    if overrides and agent_type != "download":
        return build_publish_error(
            error="dispositions are only supported for download",
            failed_step="check_dispositions_mode",
            blocking_category="dispositions_not_supported_for_run_online",
            next_step="rerun_without_dispositions_file",
        ), 1
    if deep_scan and deep_scan_findings_file:
        return build_publish_error(
            error="deep_scan and deep_scan_findings_file cannot be used together",
            failed_step="check_deep_scan_arguments",
            blocking_category="invalid_deep_scan_arguments",
            next_step="complete_deep_scan_before_findings_submission",
        ), 1
    if deep_scan and environment_selection_file:
        return build_publish_error(
            error="deep_scan and environment_selection_file cannot be used together",
            failed_step="check_environment_selection_arguments",
            blocking_category="invalid_environment_selection_arguments",
            next_step="complete_deep_scan_before_environment_selection",
        ), 1
    if environment_selection_file and agent_type != "run_online":
        return build_publish_error(
            error="environment selection is only supported for run_online",
            failed_step="check_environment_selection_mode",
            blocking_category="environment_selection_not_supported_for_download",
            next_step="rerun_without_environment_selection_file",
        ), 1
    try:
        findings = load_deep_scan_findings_file(deep_scan_findings_file)
    except ValueError as exc:
        return build_publish_error(
            error=str(exc),
            failed_step="load_deep_scan_findings",
            blocking_category="invalid_deep_scan_findings",
            next_step="fix_deep_scan_findings_then_retry",
        ), 1
    return profile.prepare(
        PrepareContext(
            agent_id=agent_id,
            latest_state=latest_state,
            manifest=manifest,
            deep_scan=deep_scan,
            overrides=overrides,
            deep_scan_findings=findings,
            environment_selection_file=environment_selection_file,
        )
    )


__all__ = ["run_prepare"]
