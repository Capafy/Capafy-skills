from __future__ import annotations
from typing import Optional

import json
import re
from collections.abc import Callable
from pathlib import Path

from packaging._shared.common.constants import ANTHROPIC_OFFICIAL_URL
from packaging._shared.common.json_walk import iter_json_string_leaves
from packaging._shared.common.url_values import build_config_url_proxy_group
from packaging.configure.scan.env_scan_rules import (
    candidate_source,
    config_literal_candidate_kind,
    is_endpoint_config_key,
)
from packaging.configure.scan.secret_context import CONTEXTUAL_KEY_SECRET_MARKERS
from packaging.configure.scan.support import append_candidate
from packaging.configure.sensitive.keywords import (
    contains_explicit_secret_keyword,
    key_tokens,
    normalize_key_name,
)
from packaging.configure.sensitive.literals import (
    extract_assignment_value,
    extract_secret_value,
    infer_managed_value_type,
    looks_like_placeholder_value,
    looks_like_platform_managed_placeholder_value,
    looks_like_secret_literal,
    looks_like_url_or_dsn,
)
from packaging.configure.runtimes.claude_code.auth import (
    CLAUDE_AUTH_ENV_KEY,
    CLAUDE_AUTH_TOKEN_ENV_KEY,
    CLAUDE_BASE_URL_ENV_KEY,
    should_skip_claude_login_structured_scan,
)


CLAUDE_NATIVE_CONFIG_BASENAMES = {
    ".claude.json",
    "settings.json",
    "settings.local.json",
    "managed-settings.json",
}
CLAUDE_NATIVE_GENERIC_SECRET_KEYS = {"apiKey", "api_key", "authToken", "auth_token"}
CLAUDE_NATIVE_GENERIC_URL_KEYS = {"baseUrl", "baseURL", "base_url"}
CLAUDE_SETTINGS_ENV_TOKEN_KEYS = (
    CLAUDE_AUTH_TOKEN_ENV_KEY,
    CLAUDE_AUTH_ENV_KEY,
)
CLAUDE_SETTINGS_ENV_KEYS = set(CLAUDE_SETTINGS_ENV_TOKEN_KEYS) | {CLAUDE_BASE_URL_ENV_KEY}
CLAUDE_LOGIN_STATE_PARENT_MARKERS = {
    "oauth",
    "oauthaccount",
    "oauthsession",
    "session",
    "sessions",
}
CLAUDE_LOGIN_STATE_SECRET_KEYS = {
    "accesstoken",
    "refreshtoken",
    "idtoken",
    "sessiontoken",
    "sessionsecret",
    "authorization",
}
def should_scan_claude_structured_values(relpath: str) -> bool:
    if should_skip_claude_login_structured_scan(relpath):
        return False
    return Path(str(relpath or "")).name not in CLAUDE_NATIVE_CONFIG_BASENAMES


def should_skip_claude_login_state_leaf(path_name: str, path_parts: list[str], key: str) -> bool:
    if path_name != ".claude.json":
        return False
    normalized_key = normalize_key_name(key)
    if normalized_key in CLAUDE_LOGIN_STATE_SECRET_KEYS:
        return True
    parent_tokens = {normalize_key_name(part) for part in path_parts[:-1] if not part.startswith("[")}
    return bool(parent_tokens & CLAUDE_LOGIN_STATE_PARENT_MARKERS) and contains_explicit_secret_keyword(key)


def is_contextual_secret_key(path_parts: list[str], key: str) -> bool:
    if "key" not in set(key_tokens(key)) and normalize_key_name(key) != "key":
        return False
    context_tokens = {
        normalize_key_name(part)
        for part in [*path_parts[:-1], *key_tokens(key)]
        if part and not str(part).startswith("[")
    }
    return bool(context_tokens & CONTEXTUAL_KEY_SECRET_MARKERS)


def claude_env_service_from_key(key: str) -> str:
    normalized = normalize_key_name(key)
    if "openai" in normalized:
        return "OpenAI"
    if "anthropic" in normalized or "claude" in normalized:
        return "Anthropic"
    if "gemini" in normalized or "google" in normalized:
        return "Google"
    if "xai" in normalized:
        return "xAI"
    if "slack" in normalized:
        return "Slack"
    return key


def collect_claude_native_generic_value(
    *,
    path_name: str,
    path_parts: list[str],
    key: str,
    value: str,
    source_display_path: str,
    display_path: str,
    annotate_candidate: Callable[[dict, str], Optional[dict]],
) -> Optional[dict]:
    if path_name not in CLAUDE_NATIVE_CONFIG_BASENAMES:
        return None
    if path_parts and path_parts[0] in {"hooks", "provider", "providers"}:
        return None
    if should_skip_claude_login_state_leaf(path_name, path_parts, key):
        return None
    if len(path_parts) >= 2 and path_parts[0] == "env" and key in CLAUDE_SETTINGS_ENV_KEYS:
        return None
    if len(path_parts) >= 2 and path_parts[0] == "env":
        contextual_secret = is_contextual_secret_key(path_parts, key)
        extracted = extract_assignment_value(key, value)
        if extracted is None and contextual_secret:
            secret_value = extract_secret_value(key, value)
            if secret_value and looks_like_secret_literal(secret_value):
                extracted = secret_value
        candidate_kind = None
        if extracted is None:
            candidate_kind = config_literal_candidate_kind(key, value)
            if candidate_kind is not None:
                entry_type, value_type, extracted = candidate_kind
                metadata_url = extracted.strip() if looks_like_url_or_dsn(extracted) else "unknown"
                return annotate_candidate(
                    {
                        "entry_type": entry_type,
                        "field": key,
                        "value_type": value_type,
                        "value": extracted,
                        "service": claude_env_service_from_key(key),
                        "default_url": metadata_url,
                        "local_url": metadata_url,
                        **candidate_source(source_display_path, ".".join(path_parts)),
                        "env_name": key if re.fullmatch(r"[A-Z][A-Z0-9_]{1,127}", key) else None,
                    },
                    display_path,
                )
        if extracted is None:
            stripped = value.strip()
            if (
                not stripped
                or looks_like_placeholder_value(stripped)
                or looks_like_platform_managed_placeholder_value(stripped)
            ):
                return None
            extracted = stripped
        entry_type = "api_key" if contains_explicit_secret_keyword(key) or contextual_secret else "managed_value"
        metadata_url = extracted.strip() if looks_like_url_or_dsn(extracted) else "unknown"
        return annotate_candidate(
            {
                "entry_type": entry_type,
                "field": key,
                "value_type": None if entry_type == "api_key" else infer_managed_value_type(key, extracted),
                "value": extracted,
                "service": claude_env_service_from_key(key),
                "default_url": metadata_url,
                "local_url": metadata_url,
                **candidate_source(source_display_path, ".".join(path_parts)),
                "env_name": key if re.fullmatch(r"[A-Z][A-Z0-9_]{1,127}", key) else None,
            },
            display_path,
        )
    contextual_secret = is_contextual_secret_key(path_parts, key)
    if contextual_secret:
        extracted = extract_assignment_value(key, value)
        if extracted is None:
            secret_value = extract_secret_value(key, value)
            if secret_value and looks_like_secret_literal(secret_value):
                extracted = secret_value
        if (
            not extracted
            or looks_like_placeholder_value(extracted)
            or looks_like_platform_managed_placeholder_value(extracted)
        ):
            return None
        return annotate_candidate(
            {
                "entry_type": "api_key",
                "field": key,
                "value_type": None,
                "value": extracted,
                "service": claude_env_service_from_key(key),
                "default_url": "unknown",
                "local_url": "unknown",
                **candidate_source(source_display_path, ".".join(path_parts)),
                "env_name": None,
            },
            display_path,
        )
    if key in CLAUDE_NATIVE_GENERIC_SECRET_KEYS:
        extracted = extract_secret_value(key, value) or extract_assignment_value(key, value)
        if not extracted or looks_like_placeholder_value(extracted):
            return None
        return annotate_candidate(
            {
                "entry_type": "api_key",
                "field": key,
                "value_type": None,
                "value": extracted,
                "service": "Anthropic",
                "default_url": "unknown",
                "local_url": "unknown",
                **candidate_source(source_display_path, ".".join(path_parts)),
                "env_name": None,
            },
            display_path,
        )
    if key in CLAUDE_NATIVE_GENERIC_URL_KEYS and value.startswith(("http://", "https://")):
        return annotate_candidate(
            {
                "entry_type": "managed_value",
                "field": key,
                "value_type": "url",
                "value": value,
                "service": "Anthropic",
                "default_url": value,
                "local_url": value,
                **candidate_source(source_display_path, ".".join(path_parts)),
                "env_name": None,
            },
            display_path,
        )
    candidate_kind = config_literal_candidate_kind(key, value)
    if candidate_kind is None:
        return None
    entry_type, value_type, extracted = candidate_kind
    metadata_url = extracted.strip() if looks_like_url_or_dsn(extracted) else "unknown"
    return annotate_candidate(
        {
            "entry_type": entry_type,
            "field": key,
            "value_type": value_type,
            "value": extracted,
            "service": claude_env_service_from_key(key),
            "default_url": metadata_url,
            "local_url": metadata_url,
            **candidate_source(source_display_path, ".".join(path_parts)),
            "env_name": key if re.fullmatch(r"[A-Z][A-Z0-9_]{1,127}", key) else None,
        },
        display_path,
    )


def collect_claude_json_config_hints(
    text: str,
    display_path: str,
    source_display_path: str,
    annotate_candidate: Callable[[dict, str], Optional[dict]],
) -> tuple[dict[str, str], dict[str, str], list[dict]]:
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {}, {}, []

    if not isinstance(data, dict):
        return {}, {}, []

    env_url_hints: dict[str, str] = {}
    value_url_hints: dict[str, str] = {}
    candidates: list[dict] = []

    def _collect_claude_settings_env_hints() -> None:
        env_payload = data.get("env")
        if not isinstance(env_payload, dict):
            return

        for key, value in env_payload.items():
            if key in CLAUDE_SETTINGS_ENV_KEYS:
                continue
            if not isinstance(value, str) or not value.strip():
                continue
            if looks_like_placeholder_value(value) or looks_like_platform_managed_placeholder_value(value):
                continue
            env_url_hints.setdefault(str(key), "unknown")

        base_url = str(env_payload.get(CLAUDE_BASE_URL_ENV_KEY, "") or "").strip()
        explicit_base_url = bool(base_url) and not looks_like_platform_managed_placeholder_value(base_url)
        if not base_url:
            base_url = ANTHROPIC_OFFICIAL_URL
        token_values = [
            str(env_payload.get(token_key, "") or "").strip()
            for token_key in CLAUDE_SETTINGS_ENV_TOKEN_KEYS
        ]
        has_token_field = any(token_values)
        has_real_token = any(
            token_value and not looks_like_placeholder_value(token_value)
            for token_value in token_values
        )

        if explicit_base_url and (has_real_token or not has_token_field):
            env_group = build_config_url_proxy_group(source_display_path, "env")
            append_candidate(
                candidates,
                annotate_candidate(
                    {
                        "entry_type": "managed_value",
                        "field": CLAUDE_BASE_URL_ENV_KEY,
                        "value_type": "url",
                        "value": base_url,
                        "service": "Anthropic",
                        "default_url": base_url,
                        "local_url": base_url,
                        **candidate_source(source_display_path, f"env.{CLAUDE_BASE_URL_ENV_KEY}"),
                        "env_name": None,
                        "url_proxy_group": env_group,
                    },
                    display_path,
                )
            )

        for token_key in CLAUDE_SETTINGS_ENV_TOKEN_KEYS:
            token_value = str(env_payload.get(token_key, "") or "").strip()
            if not token_value or looks_like_placeholder_value(token_value):
                continue
            env_url_hints[token_key] = base_url
            value_url_hints[token_value] = base_url
            candidate = annotate_candidate(
                {
                    "entry_type": "api_key",
                    "field": token_key,
                    "value_type": None,
                    "value": token_value,
                    "service": "Anthropic",
                    "default_url": base_url,
                    "local_url": base_url,
                    **candidate_source(source_display_path, f"env.{token_key}"),
                    "env_name": None,
                    "url_proxy_group": build_config_url_proxy_group(source_display_path, "env"),
                },
                display_path,
            )
            append_candidate(candidates, candidate)

    _collect_claude_settings_env_hints()

    def _on_leaf(path_parts: list[str], key: str, value: str) -> None:
        json_path = ".".join(path_parts)
        path_name = Path(display_path).name
        if path_name in CLAUDE_NATIVE_CONFIG_BASENAMES:
            generic_candidate = collect_claude_native_generic_value(
                path_name=path_name,
                path_parts=path_parts,
                key=key,
                value=value,
                source_display_path=source_display_path,
                display_path=display_path,
                annotate_candidate=annotate_candidate,
            )
            if generic_candidate is not None:
                candidates.append(generic_candidate)
            return

        if len(path_parts) >= 2 and path_parts[0] == "env" and key in CLAUDE_SETTINGS_ENV_KEYS:
            return

        if should_skip_claude_login_state_leaf(path_name, path_parts, key):
            return

        if is_endpoint_config_key(key):
            if value.startswith("http://") or value.startswith("https://"):
                service = path_parts[-2] if len(path_parts) >= 2 else "unknown"
                env_url_hints[json_path] = value
                value_url_hints[value] = value
                append_candidate(
                    candidates,
                    annotate_candidate(
                        {
                            "entry_type": "managed_value",
                            "field": key,
                            "value_type": "url",
                            "value": value,
                            "service": service,
                            "default_url": value,
                            "local_url": value,
                            **candidate_source(source_display_path, ".".join(path_parts)),
                            "env_name": None,
                            "url_proxy_group": build_config_url_proxy_group(source_display_path, path_parts[:-1]),
                        },
                        display_path,
                    )
                )
            return

        is_secret = contains_explicit_secret_keyword(key)
        if not is_secret:
            return

        extracted = extract_secret_value(key, value)
        if not extracted:
            extracted = extract_assignment_value(key, value)
        if not extracted:
            return
        if looks_like_placeholder_value(extracted):
            return
        if looks_like_platform_managed_placeholder_value(extracted):
            return

        service = "unknown"
        for part in reversed(path_parts[:-1]):
            if part.startswith("["):
                continue
            cleaned = normalize_key_name(part)
            if cleaned not in {"provider", "providers", "options", "mcp", "mcpservers", "env", "config"}:
                service = part
                break

        candidate = annotate_candidate(
            {
                "entry_type": "api_key",
                "field": key,
                "value_type": None,
                "value": extracted,
                "service": service,
                "default_url": value_url_hints.get(extracted, "unknown"),
                "local_url": value_url_hints.get(extracted, "unknown"),
                **candidate_source(source_display_path, json_path),
                "env_name": None,
                "url_proxy_group": build_config_url_proxy_group(source_display_path, path_parts[:-1]),
            },
            display_path,
        )
        append_candidate(candidates, candidate)

    for path_parts, key, value in iter_json_string_leaves(data):
        _on_leaf(path_parts, key, value)
    return env_url_hints, value_url_hints, candidates


__all__ = [
    "CLAUDE_LOGIN_STATE_PARENT_MARKERS",
    "CLAUDE_LOGIN_STATE_SECRET_KEYS",
    "CLAUDE_NATIVE_CONFIG_BASENAMES",
    "CLAUDE_NATIVE_GENERIC_SECRET_KEYS",
    "CLAUDE_NATIVE_GENERIC_URL_KEYS",
    "CLAUDE_SETTINGS_ENV_KEYS",
    "CLAUDE_SETTINGS_ENV_TOKEN_KEYS",
    "CONTEXTUAL_KEY_SECRET_MARKERS",
    "claude_env_service_from_key",
    "collect_claude_json_config_hints",
    "collect_claude_native_generic_value",
    "is_contextual_secret_key",
    "should_scan_claude_structured_values",
    "should_skip_claude_login_state_leaf",
]
