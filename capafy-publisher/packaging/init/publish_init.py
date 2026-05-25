from __future__ import annotations

from typing import Any, Optional

from packaging._shared.common.cli import build_publish_error, emit_json
from packaging._shared.common.constants import DEVELOPER_WORK_DIR_PATH
from packaging._shared.contracts.publish_work_state import (
    classify_publish_work_state_cleanup_error,
    cleanup_summary_from_existing_publish_work_state,
    summarize_publish_work_state,
)
from packaging.init.env import prepare_environment
from packaging.init.selection_discovery import (
    resolve_skills_for_target,
)
from packaging.init.explicit_skill import (
    discovery_payload_from_explicit_skill,
    explicit_skill_for_manifest,
    resolve_explicit_skill,
)
from packaging.init.local_state import (
    cleanup_previous_publish_work_state,
    write_init_completed_manifest,
)
from packaging.init.login_state import platform_login_error
from packaging.init.submit import publish_init_submit


def _run_publish_init(
    *,
    env_id: str,
    runtime_dir: str,
    skill_dir: Optional[str] = None,
    agent_id: Optional[str] = None,
    selections_json: Optional[str] = None,
) -> tuple[dict[str, Any], int]:
    env = prepare_environment(env_id, runtime_dir=runtime_dir)

    resolved_env_id = env["env_id"]
    explicit_skill: Optional[dict[str, Any]] = None
    if skill_dir:
        try:
            explicit_skill = resolve_explicit_skill(
                skill_dir,
                env_id=str(env.get("resolved_target", "") or resolved_env_id),
            )
        except ValueError as exc:
            return build_publish_error(
                error=str(exc),
                failed_step="resolve_skill_dir",
                blocking_category="invalid_skill_dir",
                developer_next_steps=[
                    "Pass --skill-dir as the single skill source directory that contains SKILL.md.",
                    "Do not pass a parent skills directory or the runtime workspace as --skill-dir.",
                ],
                next_step="fix_skill_dir_then_retry_publish_init",
                env_id=resolved_env_id,
            ), 1

    if selections_json is None:
        if explicit_skill:
            return discovery_payload_from_explicit_skill(explicit_skill), 1
        return _build_selection_discovery_payload(
            resolved_env_id=resolved_env_id,
            discovery_target=str(env.get("resolved_target", "")).strip() or resolved_env_id,
            runtime_dir=str(env.get("runtime_dir", "")).strip(),
        )

    payload, code = publish_init_submit(
        env=env,
        resolved_env_id=resolved_env_id,
        selections_json=selections_json,
        explicit_skill=explicit_skill,
        agent_id=agent_id,
    )
    if code != 0 or not isinstance(payload, dict):
        return payload, code

    enriched_payload = dict(payload)
    enriched_payload.setdefault("env_id", resolved_env_id)
    enriched_payload.setdefault("runtime_dir", str(env.get("runtime_dir", "")).strip())
    if explicit_skill:
        enriched_payload["explicit_skill"] = explicit_skill_for_manifest(explicit_skill)
    return enriched_payload, code


def _build_selection_discovery_payload(
    *,
    resolved_env_id: str,
    discovery_target: str,
    runtime_dir: str,
) -> tuple[dict[str, Any], int]:
    try:
        discovery_payload = resolve_skills_for_target(
            target_name=discovery_target,
            runtime_dir=runtime_dir,
        )
    except ValueError as exc:
        return build_publish_error(
            error=str(exc),
            failed_step="resolve_selection_candidates",
            blocking_category="selection_discovery_failed",
            developer_next_steps=[
                "Fix the local target/runtime_dir precondition, then rerun publish-init.",
            ],
            next_step="fix_selection_discovery_then_retry",
            env_id=resolved_env_id,
        ), 1

    skills = discovery_payload.get("skills") if isinstance(discovery_payload, dict) else None
    if not isinstance(skills, list) or not any(isinstance(item, dict) for item in skills):
        return build_publish_error(
            error=(
                "publish-init did not discover any skill candidates; "
                "confirm the runtime_dir or pass --skill-dir for the single skill to publish"
            ),
            failed_step="resolve_selection_candidates",
            blocking_category="selection_discovery_empty",
            discovery_payload=discovery_payload,
            developer_next_steps=[
                "Show the empty discovery result to the creator.",
                "Ask the creator to confirm the real runtime_dir/workspace root.",
                "If they meant a local single skill, rerun publish-init with --skill-dir pointing to the skill directory that contains SKILL.md.",
            ],
            next_step="confirm_skill_source_then_retry_publish_init",
            env_id=resolved_env_id,
        ), 1

    return discovery_payload, 1


def publish_init(
    *,
    env_id: str,
    runtime_dir: str,
    skill_dir: Optional[str] = None,
    agent_id: Optional[str] = None,
    selections_json: Optional[str] = None,
    reset_local_state: bool = False,
) -> int:
    login_error = platform_login_error()
    if login_error is not None:
        emit_json(login_error)
        return 1

    cleanup_summary: Optional[dict[str, Any]] = None
    if selections_json is not None:
        existing_state = summarize_publish_work_state(DEVELOPER_WORK_DIR_PATH)
        if existing_state["blocking"] and not reset_local_state:
            emit_json(
                build_publish_error(
                    error=(
                        "recoverable local publish work state already exists; "
                        "publish-init would discard it"
                    ),
                    failed_step="cleanup_previous_publish_work_state",
                    blocking_category="existing_local_publish_state",
                    existing_state=existing_state,
                    cleanup_summary=cleanup_summary_from_existing_publish_work_state(existing_state),
                    developer_next_steps=[
                        "If this is the same agent/version, resume with `publish-configure` or `publish-ship` instead of `publish-init`.",
                        "Only rerun publish-init with --reset-local-state when you intentionally want to discard the current local staging/bundle state.",
                    ],
                    next_step="resume_or_reset_local_publish_state",
                )
            )
            return 1

        try:
            cleanup_summary = cleanup_previous_publish_work_state(DEVELOPER_WORK_DIR_PATH)
        except RuntimeError as exc:
            emit_json(
                build_publish_error(
                    error=str(exc),
                    failed_step="cleanup_previous_publish_work_state",
                    blocking_category="cleanup_previous_publish_work_state_failed",
                    existing_state=existing_state,
                    cleanup_error_kind=(
                        classify_publish_work_state_cleanup_error(exc.__cause__)
                        if isinstance(exc.__cause__, OSError)
                        else "os_error"
                    ),
                    developer_next_steps=[
                        "Resolve the local filesystem cleanup problem under .temp, then retry publish-init.",
                        "If you need the current local staging/bundle state, do not rerun publish-init until the cleanup issue is understood.",
                    ],
                    next_step="fix_local_cleanup_then_retry",
                )
            )
            return 1

    payload, code = _run_publish_init(
        env_id=env_id,
        runtime_dir=runtime_dir,
        skill_dir=skill_dir,
        agent_id=agent_id,
        selections_json=selections_json,
    )
    if code == 0 and payload.get("status") == "submitted":
        write_init_completed_manifest(payload, work_dir=DEVELOPER_WORK_DIR_PATH)
    if cleanup_summary is not None:
        payload["cleanup_summary"] = cleanup_summary
    emit_json(payload)
    return code


__all__ = [
    "publish_init",
    "publish_init_submit",
]
