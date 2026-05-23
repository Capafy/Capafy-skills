from __future__ import annotations

from typing import Any

from packaging._shared.common.cli import emit_json
from packaging._shared.common.constants import DEVELOPER_WORK_DIR_PATH
from packaging._shared.common.cli import build_publish_error
from packaging._shared.contracts.publish_work_state import (
    STAGE_BUNDLE_PREPARED,
    STAGE_CONFIG_SUBMITTED,
    STAGE_INIT_COMPLETED,
    PublishWorkStateManifestError,
    require_publish_work_state,
)
from packaging._shared.contracts.selection_groups import (
    normalize_documented_selection_groups,
    selected_items_for_group,
)
from packaging.configure.buyout.configure import load_dispose_overrides_json
from packaging.configure.contexts import ConfigureContext
from packaging.configure.sensitive.deep_scan_findings import load_deep_scan_findings_file
from packaging.configure.mode_dispatch import get_configure_mode
from packaging._shared.platform import get_latest_version
from packaging._shared.platform.runtime_mapping import parse_latest_version


_CONFIGURE_ALLOWED_STAGES = {
    STAGE_INIT_COMPLETED,
    STAGE_BUNDLE_PREPARED,
    STAGE_CONFIG_SUBMITTED,
}


def run_publish_configure(
    *,
    agent_id: str,
    overrides: dict[str, str] | None = None,
    deep_scan: bool = False,
    deep_scan_findings_file: str | None = None,
) -> tuple[dict[str, Any], int]:
    try:
        manifest = require_publish_work_state(DEVELOPER_WORK_DIR_PATH)
    except PublishWorkStateManifestError as exc:
        return build_publish_error(
            error=str(exc),
            failed_step="check_prerequisite_stage",
            blocking_category="invalid_publish_work_state_manifest",
            developer_next_steps=[
                "Fix or remove the invalid local publish work-state manifest, then retry publish-configure.",
            ],
            next_step="fix_or_remove_invalid_publish_work_state_manifest",
        ), 1

    if manifest is None or manifest.current_stage not in _CONFIGURE_ALLOWED_STAGES:
        return build_publish_error(
            error="publish-configure requires init to be completed first",
            failed_step="check_prerequisite_stage",
            blocking_category="missing_prerequisite_stage",
            developer_next_steps=[
                "Run publish-init first, complete the first platform confirmation, then retry publish-configure.",
            ],
            next_step="run_publish_init_first",
        ), 1

    if manifest.agent_id != str(agent_id or "").strip():
        return build_publish_error(
            error="agent_id does not match local publish work-state",
            failed_step="check_prerequisite_stage",
            blocking_category="agent_id_mismatch",
            developer_next_steps=[
                "Use the agent_id from the active local publish work-state, or start a new publish-init flow.",
            ],
            next_step="use_matching_agent_id_or_restart_publish_init",
        ), 1

    latest = get_latest_version(agent_id)
    latest_state = parse_latest_version(latest)
    if not latest_state.is_confirmed_skills:
        return build_publish_error(
            error="skill confirmation not completed — run publish-init first and confirm skills",
            failed_step="confirm_skills",
            blocking_category="skills_not_confirmed_on_platform",
            developer_next_steps=[
                "Complete the first webpage skill confirmation, then rerun publish-configure.",
            ],
            next_step="complete_skill_confirmation_then_retry",
        ), 1
    selection_groups = normalize_documented_selection_groups(latest_state.selection_groups)
    if not selected_items_for_group(selection_groups, "skills"):
        return build_publish_error(
            error="platform skill confirmation contains no selected skills",
            failed_step="confirm_skills",
            blocking_category="skills_empty_after_platform_confirmation",
            developer_next_steps=[
                "Do you want to select a new skill for this update? If yes, go back to the first webpage and select at least one skill.",
                "If the intended skill is missing, rerun publish-init with the correct runtime_dir or --skill-dir.",
            ],
            next_step="select_skill_then_retry_publish_configure",
            agent_id=agent_id,
            agent_version_id=latest_state.agent_version_id,
            env_id=latest_state.env_id,
            agent_type=latest_state.agent_type,
        ), 1

    agent_type = latest_state.agent_type
    try:
        mode = get_configure_mode(agent_type)
    except ValueError as exc:
        return build_publish_error(
            error=str(exc),
            failed_step="check_agent_type",
            blocking_category="unsupported_agent_type",
            next_step="fix_platform_agent_type_then_retry",
            agent_id=agent_id,
            agent_version_id=latest_state.agent_version_id,
            env_id=latest_state.env_id,
            agent_type=agent_type,
        ), 1

    if deep_scan and deep_scan_findings_file is not None:
        return build_publish_error(
            error="--deep-scan and --deep-scan-findings-file cannot be used together",
            failed_step="check_deep_scan_arguments",
            blocking_category="invalid_deep_scan_arguments",
            developer_next_steps=[
                "Run publish-configure --deep-scan first to get the LLM review boundary.",
                "After the LLM writes findings JSON, rerun publish-configure without --deep-scan and pass --deep-scan-findings-file <path>.",
            ],
            next_step="rerun_publish_configure_with_separate_deep_scan_steps",
            agent_id=agent_id,
            agent_version_id=latest_state.agent_version_id,
            env_id=latest_state.env_id,
            agent_type=agent_type,
        ), 1

    try:
        deep_scan_findings = load_deep_scan_findings_file(deep_scan_findings_file)
    except ValueError as exc:
        return build_publish_error(
            error=str(exc),
            failed_step="load_deep_scan_findings",
            blocking_category="invalid_deep_scan_findings",
            developer_next_steps=[
                'Write a JSON object with generic and env_var arrays: {"generic": [], "env_var": []}.',
                "generic items need non-empty value and source fields.",
                "env_var items need non-empty value and field (env var name).",
            ],
            next_step="fix_deep_scan_findings_then_retry",
            agent_id=agent_id,
            agent_version_id=latest_state.agent_version_id,
            env_id=latest_state.env_id,
            agent_type=agent_type,
        ), 1

    return mode.configure(
        ConfigureContext(
            agent_id=agent_id,
            latest=latest,
            latest_state=latest_state,
            manifest=manifest,
            deep_scan=deep_scan,
            overrides=overrides or {},
            deep_scan_findings=deep_scan_findings,
        )
    )


def publish_configure(
    *,
    agent_id: str,
    dispositions_file: str | None = None,
    deep_scan: bool = False,
    deep_scan_findings_file: str | None = None,
) -> int:
    run_kwargs = {
        "agent_id": agent_id,
        "overrides": load_dispose_overrides_json(dispositions_file),
        "deep_scan": deep_scan,
    }
    if deep_scan_findings_file is not None:
        run_kwargs["deep_scan_findings_file"] = deep_scan_findings_file
    payload, code = run_publish_configure(**run_kwargs)
    emit_json(payload)
    return code


__all__ = [
    "publish_configure",
    "run_publish_configure",
]
