from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional

from packaging._shared.common.json_io import load_json_object
from packaging.configure.env_values import usable_env_value, usable_process_env_value


CODEX_AUTH_ENV_KEY = "OPENAI_API_KEY"
CODEX_AUTH_OVERRIDE_ENV_KEY = "CODEX_API_KEY"
CODEX_AUTH_ACCESS_TOKEN_ENV_KEY = "CODEX_ACCESS_TOKEN"
CODEX_AUTH_PROVIDER_NAME = "publisher_openai_official"
_CODEX_CONFIG_REL_SOURCE = ".codex/config.toml"
_CODEX_API_AUTH_MODES = {"api", "api_key", "apikey"}
_CODEX_OAUTH_AUTH_MODES = {
    "agent_identity",
    "agentidentity",
    "browser",
    "chat_gpt",
    "chatgpt",
    "chatgpt_auth_tokens",
    "login",
    "oauth",
}

def _is_usable_codex_auth_key(value: object) -> bool:
    if not isinstance(value, str):
        return False
    return bool(usable_env_value(value))


def _codex_auth_mode(payload: dict[str, Any]) -> str:
    return str(payload.get("auth_mode", "") or payload.get("mode", "")).strip().lower()


def _codex_auth_openai_api_key(payload: dict[str, Any]) -> str:
    value = payload.get(CODEX_AUTH_ENV_KEY)
    if _is_usable_codex_auth_key(value):
        return str(value).strip()
    return ""


def _codex_api_key_env_value(process_env: Optional[Mapping[str, str]]) -> str:
    if process_env is None:
        return ""
    return usable_process_env_value(process_env, CODEX_AUTH_OVERRIDE_ENV_KEY)


def codex_access_token_env_detected(process_env: Optional[Mapping[str, str]]) -> bool:
    if process_env is None:
        return False
    return bool(usable_process_env_value(process_env, CODEX_AUTH_ACCESS_TOKEN_ENV_KEY))


def codex_auth_uses_oauth(payload: dict[str, Any]) -> bool:
    if not payload:
        return False
    auth_mode = _codex_auth_mode(payload)
    if auth_mode in _CODEX_API_AUTH_MODES:
        return False
    if auth_mode in _CODEX_OAUTH_AUTH_MODES:
        return True
    if auth_mode:
        return True
    if _codex_auth_openai_api_key(payload):
        return False
    tokens = payload.get("tokens")
    if isinstance(tokens, dict) and tokens:
        return True
    return False


def _stage_plan_codex_auth_json_payload(stage_plan) -> tuple[dict[str, Any], str]:
    seen: set[Path] = set()
    for file_source in getattr(stage_plan, "file_sources", []):
        target_path = getattr(file_source, "relative_target_path", Path(""))
        normalized_target = target_path.as_posix() if isinstance(target_path, Path) else str(target_path)
        normalized_target = normalized_target.strip().replace("\\", "/").lstrip("./")
        if normalized_target not in {_CODEX_CONFIG_REL_SOURCE, f"_scan_only/{_CODEX_CONFIG_REL_SOURCE}"}:
            continue
        source_file = Path(getattr(file_source, "source_file", Path(""))).expanduser()
        auth_path = source_file.parent / "auth.json"
        if auth_path in seen:
            continue
        seen.add(auth_path)
        try:
            raw_text = auth_path.read_text(encoding="utf-8") if auth_path.is_file() else ""
        except OSError:
            continue
        if not raw_text:
            continue
        return load_json_object(auth_path), raw_text
    return {}, ""


def _scan_only_codex_auth_json_payload(staging_root: Path) -> tuple[dict[str, Any], str]:
    auth_path = Path(staging_root) / "_scan_only" / ".codex" / "auth.json"
    if not auth_path.is_file():
        return {}, ""
    try:
        raw_text = auth_path.read_text(encoding="utf-8")
    except OSError:
        return {}, ""
    if not raw_text:
        return {}, ""
    return load_json_object(auth_path), raw_text


def codex_auth_api_key_value(
    staging_root: Path,
    stage_plan=None,
    *,
    process_env: Optional[Mapping[str, str]] = None,
) -> str:
    env_key = _codex_api_key_env_value(process_env)
    if env_key:
        return env_key

    payload, _raw_text = _scan_only_codex_auth_json_payload(staging_root)
    if not payload and stage_plan is not None:
        payload, _raw_text = _stage_plan_codex_auth_json_payload(stage_plan)
    if not payload:
        return ""

    auth_mode = _codex_auth_mode(payload)
    if auth_mode and auth_mode not in _CODEX_API_AUTH_MODES:
        return ""
    return _codex_auth_openai_api_key(payload)


def codex_auth_oauth_detected(staging_root: Path, stage_plan=None) -> bool:
    payload, _raw_text = _scan_only_codex_auth_json_payload(staging_root)
    if not payload and stage_plan is not None:
        payload, _raw_text = _stage_plan_codex_auth_json_payload(stage_plan)
    return codex_auth_uses_oauth(payload)


def should_skip_codex_auth_structured_scan(relpath: str) -> bool:
    normalized = str(relpath or "").replace("\\", "/").lower()
    return normalized.endswith(".codex/auth.json") or normalized.endswith("_scan_only/.codex/auth.json")


__all__ = [
    "CODEX_AUTH_ACCESS_TOKEN_ENV_KEY",
    "CODEX_AUTH_ENV_KEY",
    "CODEX_AUTH_OVERRIDE_ENV_KEY",
    "codex_access_token_env_detected",
    "codex_auth_api_key_value",
    "codex_auth_oauth_detected",
    "codex_auth_uses_oauth",
    "should_skip_codex_auth_structured_scan",
]
