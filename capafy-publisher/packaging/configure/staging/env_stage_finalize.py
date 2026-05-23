from __future__ import annotations

from pathlib import Path
from typing import Callable

from packaging.configure.sensitive.strategy_registry import apply_redaction_strategy
from packaging.configure.runtimes.codex.local_files import stage_codex_model_instructions_file
from packaging.configure.runtimes.claude_code.settings_json import drop_settings_local_permissions
from packaging._shared.contracts.stage_plan import StagePlan
from packaging._shared.runtimes.support import collect_optional_command_first_line



_StageHandler = Callable[[Path, StagePlan], dict]







def _ensure_codex_dotenv(staging_root: Path) -> bool:
    dotenv_path = staging_root / ".codex" / ".env"
    if dotenv_path.is_file():
        return False
    dotenv_path.parent.mkdir(parents=True, exist_ok=True)
    dotenv_path.write_text("", encoding="utf-8")
    return True


def _codex_finalize(
    staging_root: Path,
    stage_plan: StagePlan,
) -> dict:
    summary: dict = {
        "codex_model_instruction_files": 0,
    }
    summary["codex_dotenv_materialized"] = int(_ensure_codex_dotenv(staging_root))
    warnings: list[dict] = []
    config_path = staging_root / ".codex" / "config.toml"
    if config_path.is_file():
        summary["codex_model_instruction_files"] = stage_codex_model_instructions_file(
            config_path,
            staging_root,
            stage_plan=stage_plan,
            warnings=warnings,
        )
    if warnings:
        summary["codex_model_instruction_warnings"] = warnings
    return summary


def _claude_code_finalize(
    staging_root: Path,
    _stage_plan: StagePlan,
) -> dict:
    return {
        "claude_code_settings_local_permissions_removed": drop_settings_local_permissions(staging_root),
    }







_CLOUD_HOSTED_PACKAGING: dict[str, _StageHandler] = {
    "codex": _codex_finalize,
    "claude_code": _claude_code_finalize,
}


def _apply_profile_redactions(target, staging_root: Path) -> int:
    redactions = 0
    for redact_spec in target.profile.get("redact_files", []):
        if not isinstance(redact_spec, dict):
            continue
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
        handler = _CLOUD_HOSTED_PACKAGING.get(target.env_id)
        if handler is not None:
            result.update(handler(staging_root, stage_plan))

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
