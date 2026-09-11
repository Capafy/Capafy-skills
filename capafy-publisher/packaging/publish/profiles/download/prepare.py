from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from packaging.common.constants import (
    DEVELOPER_WORK_DIR_PATH,
)
from packaging.common.cli import build_publish_error, build_success
from packaging.publish.domain.publish_work_state import (
    PublishWorkState,
)
from packaging.publish.staging.strip import run_strip_batch
from packaging.publish.reviewed_scan import (
    apply_buyout_dispositions,
    compute_scan_digest,
    disposition_summary,
    persist_reviewed_scan,
    require_reviewed_scan_payload,
    reviewed_scan_has_final_dispositions,
)
from packaging.publish.staging.review import refresh_reviewed_scan_metadata
from packaging.publish.domain.publish_work_state import write_buyout_bundle_prepared_manifest
from packaging.publish.domain.source_snapshot import compute_publish_source_snapshot_digest


def load_dispose_overrides_json(path: Optional[str]) -> dict[str, str]:
    if not path:
        return {}
    json_path = Path(path).expanduser()
    if not json_path.is_file():
        raise ValueError(f"dispositions json file not found: {path}")
    try:
        raw_payload = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"dispositions json file is not valid JSON: {path}") from exc

    payload = raw_payload
    if isinstance(raw_payload, dict) and isinstance(raw_payload.get("dispositions"), dict):
        payload = raw_payload["dispositions"]
    if not isinstance(payload, dict):
        raise ValueError("dispositions json must be an object mapping FIELD to DISPOSITION")

    overrides: dict[str, str] = {}
    for raw_field, raw_disposition in payload.items():
        field = str(raw_field or "").strip()
        disposition = str(raw_disposition or "").strip()
        if not field or not disposition:
            raise ValueError("dispositions json entries must have non-empty FIELD and DISPOSITION")
        if disposition not in {"replace_with_placeholder", "exclude_value"}:
            raise ValueError(
                f"unsupported download disposition for {field}: {disposition}; expected replace_with_placeholder or exclude_value"
            )
        overrides[field] = disposition
    return overrides


def _write_buyout_manifest(
    *,
    ctx: Any,
    result: Any,
    reviewed_scan_payload: dict[str, Any],
    disposition_status: str,
    redaction_summary: Optional[dict[str, Any]] = None,
) -> None:
    manifest: PublishWorkState = ctx.manifest
    latest_state = ctx.latest_state
    write_buyout_bundle_prepared_manifest(
        DEVELOPER_WORK_DIR_PATH,
        manifest=manifest,
        agent_id=ctx.agent_id,
        agent_version_id=latest_state.agent_version_id,
        env_id=latest_state.env_id,
        agent_type=latest_state.agent_type,
        staging_path=result.staging_root,
        reviewed_scan_path=result.reviewed_scan_path,
        reviewed_scan_digest=compute_scan_digest(reviewed_scan_payload),
        disposition_summary=disposition_summary(reviewed_scan_payload),
        disposition_status=disposition_status,
        source_snapshot_digest=compute_publish_source_snapshot_digest(
            runtime_dir=manifest.runtime_dir,
            latest_state=latest_state,
            manifest=manifest,
        ),
        redaction_summary=redaction_summary,
    )


def _apply_download_prepare_redaction(
    *,
    staging_path: str,
    env_id: str,
    reviewed_scan_payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    staging_root = Path(str(staging_path or "").strip() or "")
    if not staging_root.is_dir():
        return reviewed_scan_payload, {}
    strip_summary = run_strip_batch(
        staging_root,
        reviewed_scan=reviewed_scan_payload,
    )
    refreshed = refresh_reviewed_scan_metadata(
        reviewed_scan_payload,
        staging_root=staging_root,
        env_id=env_id,
        agent_type="download",
    )
    return refreshed if isinstance(refreshed, dict) else reviewed_scan_payload, {
        "strip_summary": strip_summary,
    }


def run_download_prepare(ctx: Any) -> tuple[dict[str, Any], int]:
    from packaging.publish.staging.build_reviewed import build_prepare_staging

    agent_id = ctx.agent_id
    latest_state = ctx.latest_state
    try:
        result, early_response = build_prepare_staging(ctx)
    except ValueError as exc:
        return build_publish_error(
            error=str(exc),
            failed_step="stage_download",
            blocking_category="invalid_download_selection",
            developer_next_steps=[
                "Check that every selected skill exists and contains SKILL.md.",
                "Rerun publish-submit after correcting the platform selection or local skill source.",
            ],
            next_step="fix_download_selection_then_retry",
            agent_id=agent_id,
            agent_version_id=latest_state.agent_version_id,
            env_id=latest_state.env_id,
            agent_type=latest_state.agent_type,
        ), 1
    if early_response is not None:
        return early_response
    assert result is not None

    reviewed_scan_payload = result.reviewed_scan
    try:
        reviewed_scan_payload = require_reviewed_scan_payload(reviewed_scan_payload)
    except ValueError as exc:
        return build_publish_error(
            error=str(exc),
            failed_step="load_reviewed_scan",
            blocking_category="missing_reviewed_scan",
            next_step="rerun_publish_submit_and_complete_review",
        ), 1

    try:
        updated = apply_buyout_dispositions(
            reviewed_scan_payload,
            overrides=ctx.overrides or {},
        )
    except ValueError as exc:
        return build_publish_error(
            error=str(exc),
            failed_step="apply_download_dispositions",
            blocking_category="invalid_download_disposition",
            developer_next_steps=[
                "Use only replace_with_placeholder or exclude_value as download dispositions.",
            ],
            next_step="fix_dispositions_file_then_retry",
            agent_id=agent_id,
        ), 1
    redaction_summary: dict[str, Any] = {}
    if reviewed_scan_has_final_dispositions(updated):
        try:
            updated, redaction_summary = _apply_download_prepare_redaction(
                staging_path=result.staging_root,
                env_id=latest_state.env_id,
                reviewed_scan_payload=updated,
            )
        except ValueError as exc:
            return build_publish_error(
                error=str(exc),
                failed_step="prepare_redaction",
                blocking_category="prepare_redaction_failed",
                next_step="fix_disposition_then_retry_publish_prepare",
            ), 1
    persist_reviewed_scan(updated, developer_work_dir_path=DEVELOPER_WORK_DIR_PATH)
    disposition_status = "ready" if reviewed_scan_has_final_dispositions(updated) else "needs_creator_disposition"
    _write_buyout_manifest(
        ctx=ctx,
        result=result,
        reviewed_scan_payload=updated,
        disposition_status=disposition_status,
        redaction_summary=redaction_summary,
    )
    if disposition_status == "ready":
        return build_success(
            status="ready",
            agent_id=agent_id,
            disposition_summary=disposition_summary(updated),
        ), 0
    return build_publish_error(
        error="download requires creator to choose replace/exclude for each sensitive item",
        failed_step="choose_download_dispositions",
        blocking_category="missing_download_dispositions",
        developer_next_steps=[
            "Create a dispositions JSON object mapping each FIELD to replace_with_placeholder or exclude_value.",
            "Rerun publish-submit with --dispositions-file <path>.",
        ],
        next_step="provide_dispositions_file",
        agent_id=agent_id,
        disposition_summary=disposition_summary(updated),
    ), 1
