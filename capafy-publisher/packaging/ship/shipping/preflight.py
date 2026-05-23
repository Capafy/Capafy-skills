from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packaging._shared.common.constants import DEFAULT_STAGING_PATH
from packaging._shared.common.cli import build_publish_error
from packaging._shared.contracts.publish_work_state import (
    PublishWorkStateManifestError,
    PublishWorkState,
    require_publish_work_state,
)
from packaging._shared.reviewed_scan.digest import compute_scan_only_digest, compute_staging_digest
from packaging.ship.mode_dispatch import get_ship_mode
from packaging._shared.platform.runtime_mapping import parse_latest_version
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
    review_staging_root: str
    staging_root: str


def _first_failed_check(
    checks: tuple[tuple[bool, dict[str, Any]], ...],
) -> tuple[dict[str, Any], int] | None:
    for failed, error_kwargs in checks:
        if failed:
            return build_publish_error(**error_kwargs), 1
    return None


def _error_args(
    error: str,
    failed_step: str,
    blocking_category: str,
    *,
    next_step: str | None = None,
    developer_next_steps: list[str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    args: dict[str, Any] = {
        "error": error,
        "failed_step": failed_step,
        "blocking_category": blocking_category,
    }
    if next_step:
        args["next_step"] = next_step
    if developer_next_steps:
        args["developer_next_steps"] = developer_next_steps
    args.update(extra)
    return args


def prepare_ship_context(
    *,
    agent_id: str,
    latest: dict[str, Any],
    developer_work_dir_path: Path,
    default_staging_path: str = DEFAULT_STAGING_PATH,
) -> tuple[ShipContext | dict[str, Any], int]:
    latest_state = parse_latest_version(latest)
    env_id = latest_state.env_id
    agent_type = latest_state.agent_type
    mode = get_ship_mode(agent_type)

    failed_check = _first_failed_check(
        (
            (
                not latest_state.is_confirmed_skills,
                _error_args(
                    "First webpage confirm not completed",
                    "confirm_skills",
                    "skills_not_confirmed_on_platform",
                    developer_next_steps=[
                        "Complete the first webpage confirmation, then rerun `publish-ship`.",
                    ],
                    next_step="complete_skill_confirmation_then_retry",
                    agent_id=agent_id,
                ),
            ),
            (
                mode.requires_config_keys_gate and not latest_state.is_confirmed_config_keys,
                _error_args(
                    "Second webpage confirm not completed",
                    "confirm_config_keys",
                    "config_keys_not_confirmed_on_platform",
                    developer_next_steps=[
                        "Complete the second webpage confirmation, then rerun `publish-ship`.",
                    ],
                    next_step="complete_config_confirmation_then_retry",
                    agent_id=agent_id,
                ),
            ),
        )
    )
    if failed_check is not None:
        return failed_check

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

    failed_check = _first_failed_check(
        (
            (
                manifest is None,
                _error_args(
                    "publish-ship requires local publish work-state from publish-configure",
                    "load_publish_work_state_manifest",
                    "missing_publish_work_state_manifest",
                    developer_next_steps=[
                        "Run `publish-configure` to build staging and complete review/config gates, then retry `publish-ship`.",
                    ],
                    next_step="rerun_publish_configure",
                ),
            ),
        )
    )
    if failed_check is not None:
        return failed_check
    assert manifest is not None

    expected_stage = mode.ship_required_stage
    failed_check = _first_failed_check(
        (
            (
                manifest.agent_id != str(agent_id or "").strip(),
                _error_args(
                    "agent_id does not match local publish work-state",
                    "check_prerequisite_stage",
                    "agent_id_mismatch",
                    developer_next_steps=[
                        "Use the agent_id from the active local publish work-state, or restart the publish flow.",
                    ],
                    next_step="use_matching_agent_id_or_restart_publish_flow",
                ),
            ),
            (
                manifest.current_stage != expected_stage,
                _error_args(
                    f"publish-ship for {agent_type} requires {expected_stage} stage",
                    "check_prerequisite_stage",
                    "missing_prerequisite_stage",
                    developer_next_steps=[
                        "Run `publish-configure` and complete any required review/config/disposition gates, then retry `publish-ship`.",
                    ],
                    next_step="rerun_publish_configure",
                ),
            ),
        )
    )
    if failed_check is not None:
        return failed_check

    review_staging_root = manifest.staging_path or default_staging_path
    reviewed_scan_path = load_reviewed_scan_path(developer_work_dir_path=developer_work_dir_path)
    reviewed_scan = read_reviewed_scan_file(reviewed_scan_path)
    failed_check = _first_failed_check(
        (
            (
                not Path(review_staging_root).is_dir(),
                _error_args(
                    f"publish-ship for {agent_type} requires the review staging directory from publish-configure",
                    "check_review_staging",
                    "missing_review_staging",
                    developer_next_steps=[
                        "Rerun `publish-configure` to rebuild review staging and complete any required gates.",
                    ],
                    next_step="rerun_publish_configure",
                ),
            ),
            (
                not is_reviewed_scan_payload(reviewed_scan),
                _error_args(
                    f"publish-ship for {agent_type} requires reviewed-scan.json from publish-configure",
                    "load_reviewed_scan",
                    "missing_reviewed_scan",
                    developer_next_steps=[
                        "Run `publish-configure` to rebuild staging scan state before publishing.",
                    ],
                    next_step="rerun_publish_configure",
                ),
            ),
        )
    )
    if failed_check is not None:
        return failed_check
    review_binding = {
        "staging_digest": compute_staging_digest(review_staging_root),
        "scan_only_digest": compute_scan_only_digest(review_staging_root),
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
        reviewed_scan_context["staging_path"] = str(review_staging_root)
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
        review_staging_root=review_staging_root,
        staging_root=review_staging_root,
    ), 0


__all__ = ["ShipContext", "prepare_ship_context"]
