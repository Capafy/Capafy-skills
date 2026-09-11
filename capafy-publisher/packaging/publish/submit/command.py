from __future__ import annotations

from typing import Any, Optional

from packaging.common.cli import build_publish_error, emit_json
from packaging.common.constants import DEVELOPER_WORK_DIR_PATH
from packaging.publish.domain.publish_work_state import (
    PublishWorkStateManifestError,
    STAGE_SECURITY_REVIEW_REQUIRED,
    require_publish_work_state,
)
from packaging.publish.submit.continue_upload import run_continue_upload
from packaging.publish.submit.prepare import run_prepare

PUBLISH_SUBMIT_ACTIONS = ("prepare", "continue_upload")


def _load_manifest() -> tuple[Any, Optional[dict[str, Any]]]:
    try:
        return require_publish_work_state(DEVELOPER_WORK_DIR_PATH), None
    except PublishWorkStateManifestError as exc:
        return None, build_publish_error(
            error=str(exc),
            failed_step="load_publish_work_state_manifest",
            blocking_category="invalid_publish_work_state_manifest",
            next_step="fix_or_remove_invalid_publish_work_state_manifest",
        )


def _action_error(action: str) -> dict[str, Any]:
    return build_publish_error(
        error=f"unsupported publish-submit action: {action}",
        failed_step="validate_publish_submit_action",
        blocking_category="unsupported_publish_submit_action",
        developer_next_steps=[f"Use one of: {', '.join(PUBLISH_SUBMIT_ACTIONS)}."],
        next_step="use_supported_publish_submit_action",
        supported_actions=list(PUBLISH_SUBMIT_ACTIONS),
    )


def run_publish_submit(
    *,
    agent_id: str,
    action: str,
    dispositions_file: Optional[str] = None,
    deep_scan: bool = False,
    deep_scan_findings_file: Optional[str] = None,
    environment_selection_file: Optional[str] = None,
) -> tuple[dict[str, Any], int]:
    normalized_action = str(action or "").strip()
    if normalized_action not in PUBLISH_SUBMIT_ACTIONS:
        return _action_error(normalized_action), 1
    manifest, error = _load_manifest()
    if error is not None:
        return error, 1
    if manifest is None:
        next_step = (
            "run_publish_init_first"
            if normalized_action == "prepare"
            else "run_publish_submit_prepare_first"
        )
        return build_publish_error(
            error=f"publish-submit {normalized_action} requires an active local draft",
            failed_step="load_publish_work_state_manifest",
            blocking_category="missing_publish_work_state_manifest",
            next_step=next_step,
        ), 1
    if normalized_action == "prepare":
        prepare_payload, prepare_code = run_prepare(
            agent_id=agent_id,
            manifest=manifest,
            dispositions_file=dispositions_file,
            deep_scan=deep_scan,
            deep_scan_findings_file=deep_scan_findings_file,
            environment_selection_file=environment_selection_file,
        )
        prepare_payload["status_scope"] = "local_publish_submit"
        prepare_payload["publish_submit_action"] = normalized_action
        if prepare_code != 0 or prepare_payload.get("requires_action") is True:
            return prepare_payload, prepare_code
        prepare_payload["status"] = STAGE_SECURITY_REVIEW_REQUIRED
        prepare_payload["next_action"] = "continue_upload"
        return prepare_payload, 0

    payload, code = run_continue_upload(
        agent_id=agent_id,
    )
    payload = dict(payload)
    payload["status_scope"] = "local_publish_submit"
    payload["publish_submit_action"] = normalized_action
    return payload, code


def publish_submit(
    *,
    agent_id: str,
    action: str,
    dispositions_file: Optional[str] = None,
    deep_scan: bool = False,
    deep_scan_findings_file: Optional[str] = None,
    environment_selection_file: Optional[str] = None,
) -> int:
    payload, code = run_publish_submit(
        agent_id=agent_id,
        action=action,
        dispositions_file=dispositions_file,
        deep_scan=deep_scan,
        deep_scan_findings_file=deep_scan_findings_file,
        environment_selection_file=environment_selection_file,
    )
    emit_json(payload)
    return code


__all__ = ["PUBLISH_SUBMIT_ACTIONS", "publish_submit", "run_publish_submit"]
