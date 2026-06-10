from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packaging._shared.llm.official_providers import find_official_provider_by_marker
from packaging._shared.common.url_values import normalize_http_url_candidate
from packaging.configure.env_values import env_reference_name, usable_env_value


HERMES_OAUTH_REL_CANDIDATES = (
    ".hermes/credentials",
    ".hermes/oauth",
)
HERMES_OAUTH_FILE_CANDIDATES = {
    ".hermes/.anthropic_oauth.json": "publisher_anthropic_official",
    ".hermes/auth/google_oauth.json": "publisher_google_official",
}
HERMES_AUTH_JSON_REL = ".hermes/auth.json"
HERMES_DOTENV_RELPATHS = (".hermes/.env", ".env")
_AUTH_JSON_PROVIDER_NAMES = {
    "minimax-oauth": "publisher_minimax_official",
    "nous": "publisher_nous_official",
    "openai-codex": "publisher_openai_official",
    "xai-oauth": "publisher_xai_official",
}
_AUTH_PROVIDER_ALIASES = {
    "minimax-cn": "minimax",
}
_OAUTH_KEY_FIELDS = ("access_token", "accessToken", "access", "api_key", "apiKey", "token", "value")


@dataclass(frozen=True)
class HermesAuthProfileCredential:
    key: str
    base_url: str = ""
    source_env: str = ""
    api_mode: str = ""


def load_hermes_oauth_keys(ctx: Any) -> dict[str, list[str]]:
    credentials = load_hermes_auth_profile_credentials(ctx)
    return hermes_oauth_keys_from_credentials(credentials)


def hermes_oauth_keys_from_credentials(
    credentials: dict[str, list[HermesAuthProfileCredential]],
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for provider_name, items in credentials.items():
        for item in items:
            if not item.key:
                continue
            values = result.setdefault(provider_name, [])
            if item.key not in values:
                values.append(item.key)
    return result


def load_hermes_auth_profile_credentials(ctx: Any) -> dict[str, list[HermesAuthProfileCredential]]:
    result: dict[str, list[HermesAuthProfileCredential]] = {}
    staged_env = _staged_dotenv_env(ctx)
    scan_only_root = Path(ctx.scan_only_root)
    for base in (scan_only_root, Path(ctx.staging_root)):
        auth_json = Path(base) / HERMES_AUTH_JSON_REL
        if auth_json.is_file():
            process_env = dict(staged_env)
            process_env.update(dict(ctx.process_env or {}))
            _append_auth_json_oauth_keys(result, auth_json, process_env=process_env)
        if Path(base) == scan_only_root:
            for relpath in HERMES_OAUTH_REL_CANDIDATES:
                oauth_root = Path(base) / relpath
                if oauth_root.is_file():
                    _append_oauth_file(result, oauth_root)
                elif oauth_root.is_dir():
                    for path in sorted(oauth_root.rglob("*.json")):
                        _append_oauth_file(result, path)
        for relpath, provider_name in HERMES_OAUTH_FILE_CANDIDATES.items():
            oauth_file = Path(base) / relpath
            if oauth_file.is_file():
                _append_oauth_file(result, oauth_file, provider_name=provider_name)
    return result


def _append_auth_json_oauth_keys(
    result: dict[str, list[HermesAuthProfileCredential]],
    path: Path,
    *,
    process_env: dict[str, str],
) -> None:
    payload = _read_json_object(path)
    if not isinstance(payload, dict):
        return
    _append_auth_json_credential_pool(result, payload, process_env=process_env)
    _append_auth_json_provider_states(result, payload)


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _append_auth_json_credential_pool(
    result: dict[str, list[HermesAuthProfileCredential]],
    payload: dict[str, Any],
    *,
    process_env: dict[str, str],
) -> None:
    credential_pool = payload.get("credential_pool")
    if not isinstance(credential_pool, dict):
        return
    for provider_name, entries in credential_pool.items():
        normalized_provider = _normalize_pool_provider_name(provider_name)
        if not normalized_provider:
            continue
        for entry in _credential_pool_entries(entries):
            key = _extract_credential_pool_entry_key(entry, process_env=process_env)
            if not key:
                continue
            base_url = _extract_credential_pool_entry_base_url(entry)
            source_env = _extract_credential_pool_entry_source_env(entry)
            values = result.setdefault(normalized_provider, [])
            credential = HermesAuthProfileCredential(key=key, base_url=base_url, source_env=source_env)
            if credential not in values:
                values.append(credential)


def _append_auth_json_provider_states(
    result: dict[str, list[HermesAuthProfileCredential]],
    payload: dict[str, Any],
) -> None:
    providers = payload.get("providers")
    if not isinstance(providers, dict):
        return
    for provider_id, state in providers.items():
        provider_name = _AUTH_JSON_PROVIDER_NAMES.get(str(provider_id or "").strip().lower())
        if not provider_name or not isinstance(state, dict):
            continue
        key = _extract_auth_json_provider_state_key(provider_id, state)
        if not key:
            continue
        values = result.setdefault(provider_name, [])
        credential = HermesAuthProfileCredential(key=key, api_mode=_auth_json_provider_state_api_mode(provider_id))
        if credential not in values:
            values.append(credential)


def _extract_auth_json_provider_state_key(provider_id: object, state: dict[str, Any]) -> str:
    normalized = str(provider_id or "").strip().lower()
    if normalized == "nous":
        return _first_usable_value(state.get("agent_key"), state.get("access_token"))
    if normalized in {"openai-codex", "xai-oauth"}:
        tokens = state.get("tokens")
        if not isinstance(tokens, dict):
            return ""
        return usable_env_value(tokens.get("access_token"))
    if normalized == "minimax-oauth":
        return usable_env_value(state.get("access_token"))
    return ""


def _auth_json_provider_state_api_mode(provider_id: object) -> str:
    normalized = str(provider_id or "").strip().lower()
    if normalized == "minimax-oauth":
        return "anthropic_messages"
    return ""


def _first_usable_value(*values: object) -> str:
    for value in values:
        normalized = usable_env_value(value)
        if normalized:
            return normalized
    return ""


def _normalize_pool_provider_name(value: object) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    if normalized.lower().startswith("custom:"):
        suffix = normalized.split(":", 1)[1].strip()
        return f"custom:{suffix}" if suffix else ""
    spec = find_official_provider_by_marker(_AUTH_PROVIDER_ALIASES.get(normalized.lower(), normalized))
    return spec.provider_name if spec else ""


def _credential_pool_entries(value: object) -> list[object]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, dict):
        return [value]
    return []


def _extract_credential_pool_entry_key(entry: object, *, process_env: dict[str, str]) -> str:
    if isinstance(entry, str):
        env_name = env_reference_name(entry)
        if env_name:
            return usable_env_value(process_env.get(env_name))
        return usable_env_value(entry)
    if not isinstance(entry, dict):
        return ""
    for field in _OAUTH_KEY_FIELDS:
        value = usable_env_value(entry.get(field))
        if value:
            return value
    source = str(entry.get("source", "") or "").strip()
    env_name = _source_env_name(source)
    if env_name:
        return usable_env_value(process_env.get(env_name))
    return ""


def _extract_credential_pool_entry_base_url(entry: object) -> str:
    if not isinstance(entry, dict):
        return ""
    for field in ("base_url", "baseUrl", "inference_base_url", "inferenceBaseUrl"):
        value = normalize_http_url_candidate(str(entry.get(field, "") or ""))
        if value:
            return value
    return ""


def _extract_credential_pool_entry_source_env(entry: object) -> str:
    if not isinstance(entry, dict):
        return ""
    source = str(entry.get("source", "") or "").strip()
    return _source_env_name(source)


def _append_oauth_file(result: dict[str, list[HermesAuthProfileCredential]], path: Path, *, provider_name: str = "") -> None:
    provider = provider_name or _vendor_from_filename(path.stem)
    if not provider:
        return
    key = _extract_oauth_key(path)
    if not key:
        return
    values = result.setdefault(provider, [])
    credential = HermesAuthProfileCredential(key=key)
    if credential not in values:
        values.append(credential)


def _extract_oauth_key(path: Path) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""

    def walk(node: object) -> str:
        if isinstance(node, dict):
            for field in _OAUTH_KEY_FIELDS:
                value = usable_env_value(node.get(field))
                if value:
                    return value
            for value in node.values():
                found = walk(value)
                if found:
                    return found
        elif isinstance(node, list):
            for value in node:
                found = walk(value)
                if found:
                    return found
        return ""

    return walk(payload)


def _vendor_from_filename(stem: str) -> str:
    normalized = str(stem or "").strip().lower()
    spec = find_official_provider_by_marker(normalized)
    return spec.provider_name if spec else ""


def _source_env_name(value: object) -> str:
    normalized = str(value or "").strip()
    if normalized.lower().startswith("env:"):
        normalized = normalized.split(":", 1)[1].strip()
    return env_reference_name(normalized)


def _staged_dotenv_env(ctx: Any) -> dict[str, str]:
    env_context = getattr(ctx, "env_context", None)
    if env_context is None:
        return {}
    names = _auth_json_source_env_names(ctx)
    if not names:
        return {}
    return env_context.staged_dotenv_values(
        Path(ctx.staging_root),
        relpaths=HERMES_DOTENV_RELPATHS,
        names=frozenset(names),
    )


def _auth_json_source_env_names(ctx: Any) -> set[str]:
    result: set[str] = set()
    for base in (Path(ctx.scan_only_root), Path(ctx.staging_root)):
        auth_json = Path(base) / HERMES_AUTH_JSON_REL
        payload = _read_json_object(auth_json)
        credential_pool = payload.get("credential_pool")
        if not isinstance(credential_pool, dict):
            continue
        for entries in credential_pool.values():
            for entry in _credential_pool_entries(entries):
                env_name = _extract_credential_pool_entry_source_env(entry)
                if env_name:
                    result.add(env_name)
    return result


__all__ = [
    "HermesAuthProfileCredential",
    "HERMES_OAUTH_FILE_CANDIDATES",
    "HERMES_OAUTH_REL_CANDIDATES",
    "HERMES_AUTH_JSON_REL",
    "HERMES_DOTENV_RELPATHS",
    "hermes_oauth_keys_from_credentials",
    "load_hermes_auth_profile_credentials",
    "load_hermes_oauth_keys",
]
