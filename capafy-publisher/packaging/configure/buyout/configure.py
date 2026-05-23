from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packaging._shared.common.constants import (
    DEVELOPER_WORK_DIR_PATH,
)
from packaging._shared.common.cli import build_publish_error
from packaging._shared.contracts.publish_work_state import (
    PublishWorkState,
)
from packaging.configure.staging.strip.batch import run_strip_batch
from packaging._shared.reviewed_scan.io import (
    persist_reviewed_scan,
    require_reviewed_scan_payload,
)
from packaging._shared.reviewed_scan.dispose import (
    apply_buyout_dispositions,
    disposition_summary,
    reviewed_scan_has_final_dispositions,
)
from packaging.configure.deep_scan_payload import build_deep_scan_payload
from packaging.configure.staging.review import compute_scan_digest, refresh_reviewed_scan_metadata
from packaging._shared.contracts.selection_groups import validate_buyout_skill_count
from packaging.configure.work_state import write_buyout_bundle_prepared_manifest
from packaging.init.explicit_skill import (
    explicit_skill_from_manifest_extra,
    merge_external_skill_bindings_into_selection_groups,
    merge_explicit_skill_into_selection_groups,
)


def load_dispose_overrides_json(path: str | None) -> dict[str, str]:
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
                f"unsupported buyout disposition for {field}: {disposition}; expected replace_with_placeholder or exclude_value"
            )
        overrides[field] = disposition
    return overrides


def _write_buyout_manifest(
    *,
    ctx: Any,
    result: Any,
    reviewed_scan_payload: dict[str, Any],
    disposition_status: str,
    redaction_summary: dict[str, Any] | None = None,
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
        redaction_summary=redaction_summary,
    )


def _apply_buyout_configure_redaction(
    *,
    manifest: PublishWorkState,
    staging_path: str,
    env_id: str,
    reviewed_scan_payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    _ = manifest
    staging_root = Path(str(staging_path or "").strip() or "")
    if not staging_root.is_dir():
        return reviewed_scan_payload, {}
    strip_summary = run_strip_batch(
        staging_root,
        reviewed_scan=reviewed_scan_payload,
        agent_type="download",
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


def run_buyout_configure(ctx: Any) -> tuple[dict[str, Any], int]:
    from packaging.configure.staging.build_reviewed import build_staging_and_reviewed_scan

    agent_id = ctx.agent_id
    manifest = ctx.manifest
    latest_state = ctx.latest_state
    selection_groups_for_stage = merge_explicit_skill_into_selection_groups(
        latest_state.selection_groups,
        explicit_skill_from_manifest_extra(manifest.extra),
    )
    selection_groups_for_stage = merge_external_skill_bindings_into_selection_groups(
        selection_groups_for_stage,
        manifest.extra.get("external_skill_bindings") if isinstance(manifest.extra, dict) else None,
    )
    try:
        selection_groups = validate_buyout_skill_count(selection_groups_for_stage)
    except ValueError as exc:
        return build_publish_error(
            error=str(exc),
            failed_step="validate_buyout_skill_count",
            blocking_category="invalid_buyout_selection",
            developer_next_steps=[
                "Edit the first webpage selection so buyout has exactly one selected skill.",
                "Rerun publish-configure after the platform selection is corrected.",
            ],
            next_step="fix_buyout_selection_then_retry",
            agent_id=agent_id,
            agent_version_id=latest_state.agent_version_id,
            env_id=latest_state.env_id,
            agent_type=latest_state.agent_type,
        ), 1
    result, build_error = build_staging_and_reviewed_scan(
        env_id=latest_state.env_id,
        runtime_dir=manifest.runtime_dir,
        agent_type=latest_state.agent_type,
        selection_groups=selection_groups,
        deep_scan_findings=getattr(ctx, "deep_scan_findings", ()),
        developer_work_dir_path=DEVELOPER_WORK_DIR_PATH,
    )
    if build_error is not None:
        return build_error, 1
    assert result is not None

    if ctx.deep_scan:
        return build_deep_scan_payload(
            agent_id=agent_id,
            agent_version_id=latest_state.agent_version_id,
            env_id=latest_state.env_id,
            agent_type=latest_state.agent_type,
            staging_root=result.staging_root,
            reviewed_scan_path=result.reviewed_scan_path,
            reviewed_scan=result.reviewed_scan,
        ), 1

    reviewed_scan_path = result.reviewed_scan_path
    reviewed_scan_payload = result.reviewed_scan
    try:
        reviewed_scan_payload = require_reviewed_scan_payload(reviewed_scan_payload)
    except ValueError as exc:
        return build_publish_error(
            error=str(exc),
            failed_step="load_reviewed_scan",
            blocking_category="missing_reviewed_scan",
            next_step="rerun_publish_configure_and_complete_review",
        ), 1

    try:
        updated = apply_buyout_dispositions(
            reviewed_scan_payload,
            overrides=ctx.overrides or {},
        )
    except ValueError as exc:
        return build_publish_error(
            error=str(exc),
            failed_step="apply_buyout_dispositions",
            blocking_category="invalid_buyout_disposition",
            developer_next_steps=[
                "Use only replace_with_placeholder or exclude_value as buyout dispositions.",
            ],
            next_step="fix_dispositions_file_then_retry",
            agent_id=agent_id,
        ), 1
    redaction_summary: dict[str, Any] = {}
    if reviewed_scan_has_final_dispositions(updated):
        try:
            updated, redaction_summary = _apply_buyout_configure_redaction(
                manifest=manifest,
                staging_path=result.staging_root,
                env_id=latest_state.env_id,
                reviewed_scan_payload=updated,
            )
        except ValueError as exc:
            return build_publish_error(
                error=str(exc),
                failed_step="configure_redaction",
                blocking_category="configure_redaction_failed",
                next_step="fix_disposition_then_retry_publish_configure",
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
        return {
            "status": "ready",
            "agent_id": agent_id,
            "reviewed_scan_path": reviewed_scan_path,
            "disposition_summary": disposition_summary(updated),
        }, 0
    return build_publish_error(
        error="buyout requires creator to choose replace/exclude for each sensitive item",
        failed_step="choose_buyout_dispositions",
        blocking_category="missing_buyout_dispositions",
        developer_next_steps=[
            "Create a dispositions JSON object mapping each FIELD to replace_with_placeholder or exclude_value.",
            "Rerun publish-configure with --dispositions-file <path>.",
        ],
        next_step="provide_dispositions_file",
        agent_id=agent_id,
        reviewed_scan_path=reviewed_scan_path,
        disposition_summary=disposition_summary(updated),
    ), 1
