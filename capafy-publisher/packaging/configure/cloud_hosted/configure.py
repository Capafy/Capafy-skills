from __future__ import annotations

from typing import Any

from packaging._shared.common.constants import DEVELOPER_WORK_DIR_PATH
from packaging._shared.common.cli import build_publish_error
from packaging._shared.contracts.publish_work_state import (
    STAGE_BUNDLE_PREPARED,
    STAGE_CONFIG_SUBMITTED,
    write_publish_work_state_manifest,
)
from packaging._shared.contracts.reviewed_scan import (
    credential_counts,
    require_cloud_hosted_url_proxy_entries,
)
from packaging._shared.reviewed_scan.io import (
    persist_submitted_config_reviewed_scan,
    read_submitted_config_reviewed_scan_file,
    require_reviewed_scan_payload,
)
from packaging._shared.reviewed_scan.digest import compute_scan_digest
from packaging.configure.deep_scan_payload import build_deep_scan_payload
from packaging.configure.platform.config_keys_request import save_config_keys
from packaging.configure.provider_runtime_config.names import ENVIRONMENT_HINT_IGNORED_NAMES
from packaging.configure.work_state import (
    CLOUD_HOSTED_CONFIGURE_RESET_EXTRA_FIELDS,
    configure_extra_with_review_artifacts,
)
from packaging._shared.selection.explicit_skill import (
    explicit_skill_from_manifest_extra,
    merge_external_skill_bindings_into_selection_groups,
    merge_explicit_skill_into_selection_groups,
)


def build_credential_summary(counts: dict[str, Any]) -> dict[str, Any]:
    url_proxy_count = int(counts.get("url_proxy", 0) or 0)
    generic_count = int(counts.get("generic", 0) or 0)

    has_llm_provider_config = url_proxy_count > 0
    has_extra_third_party_secrets = generic_count > 0

    if has_llm_provider_config and not has_extra_third_party_secrets:
        creator_message = (
            "No additional third-party service keys were found, but cloud LLM provider configuration "
            "still needs confirmation."
        )
    elif has_llm_provider_config:
        creator_message = (
            "Cloud LLM provider configuration and additional hosted credentials "
            "need confirmation."
        )
    elif has_extra_third_party_secrets:
        creator_message = "Hosted credentials need confirmation."
    else:
        creator_message = "No hosted credentials are required for this Agent."

    return {
        "has_llm_provider_config": has_llm_provider_config,
        "has_extra_third_party_secrets": has_extra_third_party_secrets,
        "creator_message": creator_message,
        "bucket_meanings": {
            "url_proxy": "Cloud-hosted LLM provider API key plus endpoint/base URL.",
            "generic": "Other standalone secrets or sensitive configuration values.",
        },
    }


def _environment_variable_hint(result: Any, reviewed_scan_payload: dict[str, Any]) -> dict[str, Any]:
    raw_names = getattr(result, "suggested_environment_variable_names", ())
    url_proxy_names: set[str] = set()
    for entry in reviewed_scan_payload.get("url_proxy", []):
        if not isinstance(entry, dict):
            continue
        for field_name in ("api_key", "url"):
            field = entry.get(field_name)
            if not isinstance(field, dict):
                continue
            name = str(field.get("field", "") or "").strip()
            if name:
                url_proxy_names.add(name)
    names = sorted({
        str(name).strip()
        for name in raw_names
        if str(name).strip()
        and str(name).strip() not in ENVIRONMENT_HINT_IGNORED_NAMES
    })
    if not names:
        return {}
    conflicts = sorted(set(names) & url_proxy_names)
    message = (
        "The Skill may use these environment variables: "
        f"{', '.join(names)}. Add them on the webpage as needed."
    )
    if conflicts:
        message += (
            f" Warning: {', '.join(conflicts)} is also used by the cloud LLM "
            "provider configuration; entering a different value may conflict "
            "with the url_proxy configuration."
        )
    return {
        "names": names,
        "conflicts": conflicts,
        "message": message,
    }


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
        ), 0

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
    bundle_extra = configure_extra_with_review_artifacts(
        manifest.extra,
        staging_path=result.staging_root,
        reviewed_scan_path=result.reviewed_scan_path,
    )
    for field in CLOUD_HOSTED_CONFIGURE_RESET_EXTRA_FIELDS:
        bundle_extra.pop(field, None)
    write_publish_work_state_manifest(
        DEVELOPER_WORK_DIR_PATH,
        agent_id=agent_id,
        agent_version_id=agent_version_id,
        env_id=env_id,
        agent_type=agent_type,
        stage=STAGE_BUNDLE_PREPARED,
        extra=bundle_extra,
    )
    extra = configure_extra_with_review_artifacts(
        manifest.extra,
        staging_path=result.staging_root,
        reviewed_scan_path=result.reviewed_scan_path,
    )
    manifest = manifest.with_stage(STAGE_BUNDLE_PREPARED, extra=extra)
    reviewed_scan_path = result.reviewed_scan_path
    config_submitted_extra = dict(manifest.extra) if isinstance(manifest.extra, dict) else {}
    config_submitted_extra["reviewed_scan_path"] = reviewed_scan_path
    counts = credential_counts(reviewed_scan_payload)
    credential_summary = build_credential_summary(counts)
    environment_variable_hint = _environment_variable_hint(result, reviewed_scan_payload)
    configure_warnings = _review_warnings(reviewed_scan_payload)
    configure_developer_next_steps = _warning_next_steps(configure_warnings)

    submitted_reviewed_scan = read_submitted_config_reviewed_scan_file(
        agent_version_id=agent_version_id,
        developer_work_dir_path=DEVELOPER_WORK_DIR_PATH,
    )
    submitted_config_unchanged = bool(submitted_reviewed_scan) and (
        compute_scan_digest(submitted_reviewed_scan) == compute_scan_digest(reviewed_scan_payload)
    )
    if latest_state.is_confirmed_config_keys and submitted_config_unchanged:
        write_publish_work_state_manifest(
            DEVELOPER_WORK_DIR_PATH,
            agent_id=agent_id,
            agent_version_id=agent_version_id,
            env_id=env_id,
            agent_type=agent_type,
            stage=STAGE_CONFIG_SUBMITTED,
            review_url=None,
            extra=config_submitted_extra,
        )
        return {
            "status": "configured",
            "agent_id": agent_id,
            "agent_version_id": agent_version_id,
            "env_id": env_id,
            "agent_type": agent_type,
            "credential_counts": counts,
            "credential_summary": credential_summary,
            "review_url": "",
            "already_confirmed": True,
            **({"warnings": configure_warnings} if configure_warnings else {}),
            **({"developer_next_steps": configure_developer_next_steps} if configure_developer_next_steps else {}),
        }, 0

    result = save_config_keys(agent_id, agent_version_id, reviewed_scan_payload)
    persist_submitted_config_reviewed_scan(
        reviewed_scan_payload,
        agent_version_id=agent_version_id,
        developer_work_dir_path=DEVELOPER_WORK_DIR_PATH,
    )
    review_url = str(result.get("url", "")).strip()
    write_publish_work_state_manifest(
        DEVELOPER_WORK_DIR_PATH,
        agent_id=agent_id,
        agent_version_id=agent_version_id,
        env_id=env_id,
        agent_type=agent_type,
        stage=STAGE_CONFIG_SUBMITTED,
        review_url=review_url or None,
        extra=config_submitted_extra,
    )
    return {
        "status": "configured",
        "agent_id": agent_id,
        "agent_version_id": agent_version_id,
        "env_id": env_id,
        "agent_type": agent_type,
        "credential_counts": counts,
        "credential_summary": credential_summary,
        "review_url": review_url,
        **(
            {"environment_variable_hint": environment_variable_hint}
            if review_url and environment_variable_hint
            else {}
        ),
        **({"warnings": configure_warnings} if configure_warnings else {}),
        **({"developer_next_steps": configure_developer_next_steps} if configure_developer_next_steps else {}),
    }, 0


def _review_warnings(reviewed_scan_payload: dict[str, Any]) -> list[str]:
    review = reviewed_scan_payload.get("_review")
    if not isinstance(review, dict):
        return []
    warnings = review.get("warnings")
    if not isinstance(warnings, list):
        return []
    return [str(item) for item in warnings if str(item).strip()]


def _warning_next_steps(warnings: list[str]) -> list[str]:
    if not warnings:
        return []
    return [
        "Review the configuration warnings before confirming hosted LLM provider keys and endpoints.",
        *warnings,
    ]


__all__ = [
    "build_credential_summary",
    "run_cloud_hosted_configure",
]
