from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Union

from packaging._shared.common.constants import ANTHROPIC_OFFICIAL_URL
from packaging._shared.common.json_io import load_json_object
from packaging.configure.env_values import usable_env_value, usable_process_env_value
from packaging.configure.sensitive.keywords import normalize_key_name


CLAUDE_AUTH_ENV_KEY = "ANTHROPIC_API_KEY"
CLAUDE_AUTH_TOKEN_ENV_KEY = "ANTHROPIC_AUTH_TOKEN"
CLAUDE_CODE_OAUTH_TOKEN_ENV_KEY = "CLAUDE_CODE_OAUTH_TOKEN"
CLAUDE_BASE_URL_ENV_KEY = "ANTHROPIC_BASE_URL"
_CLAUDE_LOGIN_PARENT_MARKERS = {
    "oauth",
    "oauthaccount",
    "oauthsession",
    "session",
    "sessions",
    "account",
    "credentials",
}
_CLAUDE_LOGIN_SECRET_KEYS = {
    "accesstoken",
    "refreshtoken",
    "idtoken",
    "sessionkey",
    "sessiontoken",
    "sessionsecret",
    "apikey",
    "authkey",
    "authtoken",
    "api",
}


def load_claude_json(staging_root: Path) -> dict[str, Any]:
    return load_json_object(staging_root / "_scan_only" / ".claude" / ".claude.json")


def load_claude_credentials_json(staging_root: Path) -> dict[str, Any]:
    return load_json_object(staging_root / "_scan_only" / ".claude" / ".credentials.json")


def _contains_claude_login_state(node: object, parents: tuple[str, ...] = ()) -> bool:
    if isinstance(node, dict):
        for key, value in node.items():
            normalized_key = normalize_key_name(str(key))
            normalized_parents = {normalize_key_name(parent) for parent in parents}
            if normalized_key in _CLAUDE_LOGIN_PARENT_MARKERS and bool(value):
                return True
            if (
                normalized_key in _CLAUDE_LOGIN_SECRET_KEYS
                and normalized_parents & _CLAUDE_LOGIN_PARENT_MARKERS
                and bool(str(value or "").strip())
            ):
                return True
            if _contains_claude_login_state(value, (*parents, str(key))):
                return True
    elif isinstance(node, list):
        for item in node:
            if _contains_claude_login_state(item, parents):
                return True
    return False


def claude_json_uses_login_state(payload: dict[str, Any]) -> bool:
    return bool(payload and _contains_claude_login_state(payload))


def _contains_claude_credentials_login_state(node: object) -> bool:
    if isinstance(node, dict):
        for key, value in node.items():
            normalized_key = normalize_key_name(str(key))
            if normalized_key in _CLAUDE_LOGIN_SECRET_KEYS and bool(str(value or "").strip()):
                return True
            if _contains_claude_credentials_login_state(value):
                return True
    elif isinstance(node, list):
        for item in node:
            if _contains_claude_credentials_login_state(item):
                return True
    return False


def claude_credentials_uses_login_state(payload: dict[str, Any]) -> bool:
    return bool(payload and _contains_claude_credentials_login_state(payload))


def _stage_plan_credentials_payload(stage_plan) -> dict[str, Any]:
    for file_source in getattr(stage_plan, "file_sources", []):
        source_key = str(getattr(file_source, "source_key", "") or "").strip()
        target_path = getattr(file_source, "relative_target_path", Path(""))
        normalized_target = target_path.as_posix() if isinstance(target_path, Path) else str(target_path)
        if source_key != ".claude/.credentials.json" and normalized_target != ".claude/.credentials.json":
            continue
        return load_json_object(getattr(file_source, "source_file", Path("")))
    return {}


def _claude_json_explicit_base_url(payload: dict[str, Any]) -> str:
    env_payload = payload.get("env")
    if isinstance(env_payload, dict):
        return usable_env_value(env_payload.get(CLAUDE_BASE_URL_ENV_KEY, ""))
    return ""


def _is_usable_claude_json_configured_key(value: str, explicit_base_url: str) -> bool:
    if not usable_env_value(value):
        return False

    if not explicit_base_url or explicit_base_url == ANTHROPIC_OFFICIAL_URL:
        return value.lower().startswith("sk-ant-api")
    return True


def _claude_json_configured_key(payload: dict[str, Any]) -> tuple[str, str]:
    explicit_base_url = _claude_json_explicit_base_url(payload)
    env_payload = payload.get("env")
    if isinstance(env_payload, dict):
        for key in (CLAUDE_AUTH_TOKEN_ENV_KEY, CLAUDE_AUTH_ENV_KEY):
            value = str(env_payload.get(key, "") or "").strip()
            if _is_usable_claude_json_configured_key(value, explicit_base_url):
                return key, value
    return "", ""


def _claude_json_base_url(payload: dict[str, Any]) -> str:
    return _claude_json_explicit_base_url(payload) or ANTHROPIC_OFFICIAL_URL


def claude_auth_configured_key(staging_root: Path) -> tuple[str, str, str]:
    for payload in (
        load_claude_credentials_json(staging_root),
        load_claude_json(staging_root),
    ):
        if not payload:
            continue
        field, value = _claude_json_configured_key(payload)
        if not field or not value:
            continue
        return field, value, _claude_json_base_url(payload)
    return "", "", ""


def claude_auth_login_detected(staging_root: Path, stage_plan=None) -> bool:
    claude_json_payload = load_claude_json(staging_root)
    if claude_json_payload and claude_json_uses_login_state(claude_json_payload):
        return True

    credentials_payload = _stage_plan_credentials_payload(stage_plan)
    if credentials_payload and claude_credentials_uses_login_state(credentials_payload):
        return True

    credentials_payload = load_claude_credentials_json(staging_root)
    return bool(credentials_payload and claude_credentials_uses_login_state(credentials_payload))


def claude_oauth_token_env_detected(process_env: Union[Mapping[str, str], Any]) -> bool:
    return bool(usable_process_env_value(process_env, CLAUDE_CODE_OAUTH_TOKEN_ENV_KEY))


def should_skip_claude_login_structured_scan(relpath: str) -> bool:
    normalized = str(relpath or "").replace("\\", "/").lower()
    return normalized.endswith(".claude/.credentials.json") or normalized.endswith("_scan_only/.claude/.credentials.json")


__all__ = [
    "CLAUDE_AUTH_ENV_KEY",
    "CLAUDE_AUTH_TOKEN_ENV_KEY",
    "CLAUDE_CODE_OAUTH_TOKEN_ENV_KEY",
    "claude_auth_configured_key",
    "claude_auth_login_detected",
    "claude_oauth_token_env_detected",
    "claude_credentials_uses_login_state",
    "claude_json_uses_login_state",
    "should_skip_claude_login_structured_scan",
]
