from __future__ import annotations

from typing import Any

from packaging.common.constants import DEVELOPER_WORK_DIR_PATH
from packaging.common.cli import build_publish_error, build_success
from packaging.publish.domain.publish_work_state import (
    STAGE_SECURITY_REVIEW_REQUIRED,
    write_publish_work_state_manifest,
)
from packaging.publish.reviewed_scan import (
    compute_scan_digest,
    credential_counts,
    require_reviewed_scan_payload,
)
from packaging.publish.platform.environment_selection import (
    compute_candidate_digest,
    compute_selection_digest,
    filter_environment_names_for_runtime,
    load_environment_selection,
    normalize_environment_names,
    read_selected_environment_values,
    write_candidate_file,
)
from packaging.publish.platform.url_proxy_environment import ENVIRONMENT_HINT_IGNORED_NAMES
from packaging.publish.domain.source_snapshot import compute_publish_source_snapshot_digest
from packaging.publish.domain.publish_work_state import (
    RUN_ONLINE_PREPARE_RESET_EXTRA_FIELDS,
    prepare_extra_with_staging,
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
            "url_proxy": "Current LLM route metadata: endpoint/base URL, model, and API format.",
            "generic": "Other standalone secrets or sensitive configuration values.",
        },
    }


def _environment_variable_hint(
    result: Any,
    reviewed_scan_payload: dict[str, Any],
    *,
    env_id: str,
) -> dict[str, Any]:
    raw_names = getattr(result, "suggested_environment_variable_names", ())
    url_proxy_names: set[str] = set()
    for entry in reviewed_scan_payload.get("url_proxy", []):
        if not isinstance(entry, dict):
            continue
        field = entry.get("url")
        if not isinstance(field, dict):
            continue
        name = str(field.get("field", "") or "").strip()
        if name:
            url_proxy_names.add(name)
    names = sorted(
        {
            str(name).strip()
            for name in filter_environment_names_for_runtime(raw_names, env_id=env_id)
            if str(name).strip() not in ENVIRONMENT_HINT_IGNORED_NAMES
        }
    )
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


def _eligible_environment_names(
    result: Any,
    reviewed_scan_payload: dict[str, Any],
    *,
    env_id: str,
) -> tuple[str, ...]:
    raw_names = getattr(result, "suggested_environment_variable_names", ())
    filtered_names = filter_environment_names_for_runtime(raw_names, env_id=env_id)
    names = set(normalize_environment_names(filtered_names, label="environment candidates"))
    covered_names: set[str] = set()
    for entry in reviewed_scan_payload.get("url_proxy", []):
        if not isinstance(entry, dict):
            continue
        field = entry.get("url")
        if isinstance(field, dict):
            value = str(field.get("field", "") or "").strip().upper()
            if value:
                covered_names.add(value)
    for entry in reviewed_scan_payload.get("generic", []):
        if isinstance(entry, dict):
            value = str(entry.get("field", "") or "").strip().upper()
            if value:
                covered_names.add(value)
    return tuple(sorted(names - covered_names))


def _environment_selection_error_category(error: Exception) -> str:
    message = str(error)
    if "does not exist" in message or "failed to read" in message:
        return "invalid_environment_selection_file"
    if "candidates changed" in message:
        return "environment_candidates_changed"
    if "subset" in message:
        return "environment_selection_not_subset"
    if "forbidden" in message:
        return "environment_variable_forbidden"
    if "missing locally" in message:
        return "selected_environment_variables_missing"
    return "invalid_environment_selection_file"


def run_run_online_prepare(ctx: Any) -> tuple[dict[str, Any], int]:
    from packaging.publish.staging.build_reviewed import build_prepare_staging

    agent_id = ctx.agent_id
    manifest = ctx.manifest
    latest_state = ctx.latest_state
    agent_version_id = latest_state.agent_version_id
    env_id = latest_state.env_id
    agent_type = latest_state.agent_type
    result, early_response = build_prepare_staging(ctx)
    if early_response is not None:
        return early_response
    assert result is not None

    reviewed_scan_payload = result.reviewed_scan
    try:
        reviewed_scan_payload = require_reviewed_scan_payload(reviewed_scan_payload)
    except ValueError as exc:
        return build_publish_error(
            error=f"invalid reviewed scan payload: {exc}",
            failed_step="load_reviewed_scan",
            blocking_category="invalid_reviewed_scan",
            developer_next_steps=[
                "Rerun publish-submit to regenerate reviewed-scan.json from the latest staging scan.",
            ],
            next_step="rerun_publish_submit",
        ), 1

    environment_candidates = _eligible_environment_names(
        result,
        reviewed_scan_payload,
        env_id=env_id,
    )
    staging_digest = str(getattr(result, "staging_digest", "") or "").strip()
    environment_candidate_digest = compute_candidate_digest(
        environment_candidates,
        staging_digest=staging_digest,
        env_id=env_id,
        agent_type=agent_type,
    )
    environment_selection = None
    environment_variables: list[dict[str, str]] = []
    if getattr(ctx, "environment_selection_file", None):
        try:
            environment_selection = load_environment_selection(
                str(ctx.environment_selection_file),
                expected_candidates=environment_candidates,
                expected_digest=environment_candidate_digest,
            )
            environment_variables = read_selected_environment_values(environment_selection)
            environment_selection_path = environment_selection.path
        except ValueError as exc:
            return build_publish_error(
                error=str(exc),
                failed_step="load_environment_selection",
                blocking_category=_environment_selection_error_category(exc),
                developer_next_steps=[
                    "Use the environment selection file generated by the latest publish-submit run.",
                    "Only edit the selected array; do not edit candidates or candidate_digest.",
                    "Set every selected environment variable locally, then retry publish-submit.",
                ],
                next_step="fix_environment_selection_then_retry",
                agent_id=agent_id,
                agent_version_id=agent_version_id,
                env_id=env_id,
                agent_type=agent_type,
            ), 1
    else:
        environment_selection_path = str(
            write_candidate_file(
                DEVELOPER_WORK_DIR_PATH,
                agent_version_id=agent_version_id,
                candidates=environment_candidates,
                candidate_digest=environment_candidate_digest,
            )
        )

    environment_selection_digest = (
        compute_selection_digest(environment_selection)
        if environment_selection is not None and environment_selection.selected
        else ""
    )
    environment_selection_summary = {
        "optional": True,
        "file": environment_selection_path,
        "candidate_count": len(environment_candidates),
        "selected_count": len(environment_selection.selected) if environment_selection else 0,
        "local_upload_requested": bool(environment_variables),
    }

    bundle_extra = prepare_extra_with_staging(
        manifest.extra,
        staging_path=result.staging_root,
    )
    for field in RUN_ONLINE_PREPARE_RESET_EXTRA_FIELDS:
        bundle_extra.pop(field, None)
    reviewed_scan_digest = compute_scan_digest(reviewed_scan_payload)
    bundle_extra.update(
        {
            "staging_digest": staging_digest,
            "reviewed_scan_path": result.reviewed_scan_path,
            "reviewed_scan_digest": reviewed_scan_digest,
            "environment_candidates_path": environment_selection_path,
            "environment_candidate_digest": environment_candidate_digest,
            "source_snapshot_digest": compute_publish_source_snapshot_digest(
                runtime_dir=manifest.runtime_dir,
                latest_state=latest_state,
                manifest=manifest,
            ),
        }
    )
    if environment_variables:
        bundle_extra["environment_variables"] = environment_variables
    else:
        bundle_extra.pop("environment_variables", None)
    if environment_selection is not None:
        bundle_extra["environment_selection_path"] = environment_selection_path
    if environment_selection_digest:
        bundle_extra["environment_selection_digest"] = environment_selection_digest

    write_publish_work_state_manifest(
        DEVELOPER_WORK_DIR_PATH,
        agent_id=agent_id,
        agent_version_id=agent_version_id,
        env_id=env_id,
        agent_type=agent_type,
        stage=STAGE_SECURITY_REVIEW_REQUIRED,
        review_url=None,
        extra=bundle_extra,
    )

    counts = credential_counts(reviewed_scan_payload)
    credential_summary = build_credential_summary(counts)
    environment_variable_hint = _environment_variable_hint(
        result,
        reviewed_scan_payload,
        env_id=env_id,
    )
    prepare_warnings = _review_warnings(reviewed_scan_payload)
    prepare_developer_next_steps = _warning_next_steps(prepare_warnings)
    return build_success(
        status="security_ready",
        status_scope="local_publish_submit",
        agent_id=agent_id,
        agent_version_id=agent_version_id,
        env_id=env_id,
        agent_type=agent_type,
        credential_counts=counts,
        credential_summary=credential_summary,
        review_url="",
        security_ready=True,
        staging_digest=staging_digest,
        reviewed_scan_digest=reviewed_scan_digest,
        environment_selection=environment_selection_summary,
        **(
            {"environment_variable_hint": environment_variable_hint}
            if environment_variable_hint
            else {}
        ),
        **({"warnings": prepare_warnings} if prepare_warnings else {}),
        **(
            {"developer_next_steps": prepare_developer_next_steps}
            if prepare_developer_next_steps
            else {}
        ),
    ), 0

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
    "run_run_online_prepare",
]
