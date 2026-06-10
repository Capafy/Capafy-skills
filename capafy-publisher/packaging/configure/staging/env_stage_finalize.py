from __future__ import annotations

from pathlib import Path

from packaging.configure.sensitive.strategy_registry import apply_redaction_strategy
from packaging._shared.env_profiles.config_files import collect_redacted_config_files
from packaging._shared.contracts.stage_plan import StagePlan
from packaging._shared.runtimes.contracts import call_optional_target_hook
from packaging._shared.runtimes.support import collect_optional_command_first_line


def _apply_profile_redactions(target, staging_root: Path) -> int:
    redactions = 0
    for redact_spec in collect_redacted_config_files(target.profile):
        target_path = staging_root / str(redact_spec.get("target_path", ""))
        if not target_path.is_file():
            continue
        redactions += apply_redaction_strategy(
            str(redact_spec.get("strategy", "")),
            target_path,
            source=str(redact_spec.get("target_path", "")),
        )
    return redactions


def finalize_packaging(
    target,
    staging_root: Path,
    stage_plan: StagePlan,
    *,
    agent_type: str = "",
) -> dict:
    result: dict = {}
    if agent_type == "run_online":
        result.update(
            call_optional_target_hook(
                target,
                "finalize_cloud_hosted_packaging",
                staging_root,
                stage_plan,
                default={},
            )
        )
    result[f"{target.env_id}_redactions"] = _apply_profile_redactions(target, staging_root)

    return result


def collect_runtime_environment_fields(target) -> dict:
    runtime_env = target.profile.get("runtime_env", {})
    if not isinstance(runtime_env, dict):
        return {}
    field = runtime_env.get("field")
    command = runtime_env.get("command")
    if not field or not isinstance(command, list) or not command:
        return {}
    return {str(field): collect_optional_command_first_line([str(item) for item in command])}


__all__ = [
    "collect_runtime_environment_fields",
    "finalize_packaging",
]
