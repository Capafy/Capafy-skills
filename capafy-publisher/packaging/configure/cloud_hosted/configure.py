from __future__ import annotations

from typing import Any, Optional

from packaging._shared.common.constants import DEVELOPER_WORK_DIR_PATH
from packaging._shared.common.cli import build_publish_error
from packaging._shared.contracts.publish_work_state import (
    STAGE_BUNDLE_PREPARED,
    PublishWorkState,
)
from packaging._shared.contracts.reviewed_scan import (
    credential_counts,
    require_cloud_hosted_url_proxy_entries,
)
from packaging._shared.platform import save_config_keys
from packaging._shared.reviewed_scan.io import require_reviewed_scan_payload
from packaging.configure.deep_scan_payload import build_deep_scan_payload
from packaging.configure.work_state import (
    configure_extra_with_review_artifacts,
    write_cloud_hosted_bundle_prepared_manifest,
    write_cloud_hosted_config_submitted_manifest,
)
from packaging.init.explicit_skill import (
    explicit_skill_from_manifest_extra,
    merge_external_skill_bindings_into_selection_groups,
    merge_explicit_skill_into_selection_groups,
)


def run_cloud_hosted_configure(ctx: Any) -> tuple[dict[str, Any], int]:
    from packaging.configure.staging.build_reviewed import build_staging_and_reviewed_scan

    agent_id = ctx.agent_id
    manifest = ctx.manifest
    latest_state = ctx.latest_state
    agent_version_id = latest_state.agent_version_id
    env_id = latest_state.env_id
    agent_type = latest_state.agent_type
    selection_groups = merge_explicit_skill_into_selection_groups(
        latest_state.selection_groups,
        explicit_skill_from_manifest_extra(manifest.extra),
    )
    selection_groups = merge_external_skill_bindings_into_selection_groups(
        selection_groups,
        manifest.extra.get("external_skill_bindings") if isinstance(manifest.extra, dict) else None,
    )

    result, build_error = build_staging_and_reviewed_scan(
        env_id=env_id,
        runtime_dir=manifest.runtime_dir,
        agent_type=agent_type,
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
            agent_version_id=agent_version_id,
            env_id=env_id,
            agent_type=agent_type,
            staging_root=result.staging_root,
            reviewed_scan_path=result.reviewed_scan_path,
            reviewed_scan=result.reviewed_scan,
        ), 1

    reviewed_scan_payload = result.reviewed_scan



    try:
        reviewed_scan_payload = require_reviewed_scan_payload(reviewed_scan_payload)
    except ValueError as exc:
        return build_publish_error(
            error=f"invalid reviewed scan payload: {exc}",
            failed_step="load_reviewed_scan",
            blocking_category="invalid_reviewed_scan",
            developer_next_steps=[
                "Rerun publish-configure to regenerate reviewed-scan.json from the latest staging scan.",
            ],
            next_step="rerun_publish_configure",
        ), 1
    try:
        require_cloud_hosted_url_proxy_entries(reviewed_scan_payload)
    except ValueError as exc:
        return build_publish_error(
            error=str(exc),
            failed_step="configure_url_proxy_gate",
            blocking_category="missing_required_url_proxy",
            developer_next_steps=[
                "Re-run publish-configure after configuring at least one LLM provider with an endpoint URL and API key.",
            ],
            agent_id=agent_id,
            agent_version_id=agent_version_id,
            env_id=env_id,
            agent_type=agent_type,
            reviewed_scan_path=result.reviewed_scan_path,
            credential_counts=credential_counts(reviewed_scan_payload),
        ), 1
    _write_bundle_prepared_manifest(
        ctx=ctx,
        result=result,
    )
    extra = configure_extra_with_review_artifacts(
        manifest.extra,
        staging_path=result.staging_root,
        reviewed_scan_path=result.reviewed_scan_path,
    )
    manifest = manifest.with_stage(STAGE_BUNDLE_PREPARED, extra=extra)
    reviewed_scan_path = result.reviewed_scan_path

    if latest_state.is_confirmed_config_keys:
        _write_config_submitted_manifest(
            manifest=manifest,
            agent_id=agent_id,
            agent_version_id=agent_version_id,
            env_id=env_id,
            agent_type=agent_type,
            review_url=None,
            reviewed_scan_path=reviewed_scan_path,
        )
        return {
            "status": "configured",
            "agent_id": agent_id,
            "agent_version_id": agent_version_id,
            "env_id": env_id,
            "agent_type": agent_type,
            "credential_counts": credential_counts(reviewed_scan_payload),
            "review_url": "",
            "already_confirmed": True,
        }, 0

    result = save_config_keys(agent_id, agent_version_id, reviewed_scan_payload)
    review_url = str(result.get("url", "")).strip()
    _write_config_submitted_manifest(
        manifest=manifest,
        agent_id=agent_id,
        agent_version_id=agent_version_id,
        env_id=env_id,
        agent_type=agent_type,
        review_url=review_url or None,
        reviewed_scan_path=reviewed_scan_path,
    )
    return {
        "status": "configured",
        "agent_id": agent_id,
        "agent_version_id": agent_version_id,
        "env_id": env_id,
        "agent_type": agent_type,
        "credential_counts": credential_counts(reviewed_scan_payload),
        "review_url": review_url,
    }, 0


def _write_bundle_prepared_manifest(
    *,
    ctx: Any,
    result: Any,
) -> None:
    manifest: PublishWorkState = ctx.manifest
    latest_state = ctx.latest_state
    write_cloud_hosted_bundle_prepared_manifest(
        DEVELOPER_WORK_DIR_PATH,
        manifest=manifest,
        agent_id=ctx.agent_id,
        agent_version_id=latest_state.agent_version_id,
        env_id=latest_state.env_id,
        agent_type=latest_state.agent_type,
        staging_path=result.staging_root,
        reviewed_scan_path=result.reviewed_scan_path,
    )


def _write_config_submitted_manifest(
    *,
    manifest: PublishWorkState,
    agent_id: str,
    agent_version_id: str,
    env_id: str,
    agent_type: str,
    review_url: Optional[str],
    reviewed_scan_path: str,
) -> None:
    write_cloud_hosted_config_submitted_manifest(
        DEVELOPER_WORK_DIR_PATH,
        manifest=manifest,
        agent_id=agent_id,
        agent_version_id=agent_version_id,
        env_id=env_id,
        agent_type=agent_type,
        review_url=review_url,
        reviewed_scan_path=reviewed_scan_path,
    )


__all__ = [
    "run_cloud_hosted_configure",
]
