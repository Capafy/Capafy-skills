from __future__ import annotations

import json
from typing import Any, Optional

from packaging.configure.env_values import usable_env_value


OPENCLAW_AUTH_PROFILE_REL = ".openclaw/agents/main/agent/auth-profiles.json"

_AUTH_PROFILE_NON_PROVIDER_TOKENS = frozenset({
    "api_key",
    "apikey",
    "auth",
    "default",
    "key",
    "profile",
    "profiles",
})


def load_auth_profile_keys(ctx: Any) -> dict[str, list[str]]:
    for base in (ctx.scan_only_root, ctx.staging_root):
        path = base / OPENCLAW_AUTH_PROFILE_REL
        if path.is_file():
            break
    else:
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    result: dict[str, list[str]] = {}

    def extract_key(node: dict) -> Optional[str]:
        for field in ("key", "apiKey", "api_key", "apikey"):
            value = node.get(field)
            if not isinstance(value, str):
                continue
            normalized = usable_env_value(value)
            if normalized:
                return normalized
        return None

    def walk(node: Any, parts: list[str]) -> None:
        if isinstance(node, dict):
            provider = _infer_auth_profile_provider_name(node, parts)
            if provider:
                key = extract_key(node)
                if key:
                    result.setdefault(provider, []).append(key)
            for key, value in node.items():
                walk(value, parts + [str(key)])
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, parts + [str(index)])

    walk(payload, [])
    return result


def _normalize_auth_profile_provider_name(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.split(":", 1)[0].strip()
    if not text or text.lower() in _AUTH_PROFILE_NON_PROVIDER_TOKENS:
        return ""
    return text


def _infer_auth_profile_provider_name(node: dict, parts: list[str]) -> Optional[str]:
    for key in ("provider", "service", "name", "api"):
        candidate = _normalize_auth_profile_provider_name(node.get(key))
        if candidate:
            return candidate
    for part in reversed(parts):
        candidate = _normalize_auth_profile_provider_name(part)
        if candidate:
            return candidate
    return None


__all__ = [
    "OPENCLAW_AUTH_PROFILE_REL",
    "load_auth_profile_keys",
]
