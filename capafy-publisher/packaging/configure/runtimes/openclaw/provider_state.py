from __future__ import annotations

from typing import Any

from packaging._shared.common.url_values import normalize_http_url_candidate
from packaging._shared.openclaw.official_providers import (
    OPENCLAW_OFFICIAL_PROVIDER_SPECS,
    OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME,
    find_openclaw_official_provider_by_marker,
    find_openclaw_official_provider_in_text,
)
from packaging.configure.runtimes.openclaw.provider_keys import (
    collect_provider_api_key_items_by_priority,
)
from packaging.configure.runtimes.openclaw.provider_usage import (
    api_format_from_openclaw_provider,
    get_openclaw_providers,
)


_LOGIN_PLUGIN_STATE_KEYS = frozenset({
    "accessToken",
    "access_token",
    "apiKey",
    "api_key",
    "auth",
    "credential",
    "credentials",
    "idToken",
    "id_token",
    "login",
    "refreshToken",
    "refresh_token",
    "session",
    "token",
})
_KNOWN_LOGIN_PLUGIN_ENTRIES = frozenset({
    "anthropic",
    "claude",
    "gemini",
    "github-copilot",
    "google",
    "openai",
})
_LOGIN_PROVIDER_SIGNAL_KEYS = frozenset({
    "api",
    "name",
    "provider",
    "service",
})


def _looks_like_login_plugin_entry(plugin_name: object, payload: object) -> bool:
    normalized_name = str(plugin_name or "").strip().lower()
    if not normalized_name:
        return False
    if normalized_name in _KNOWN_LOGIN_PLUGIN_ENTRIES or normalized_name.endswith("login"):
        return True
    if isinstance(payload, dict):
        if any(str(key) in _LOGIN_PLUGIN_STATE_KEYS for key in payload):
            return True
    return False


def _official_provider_name_from_login_value(value: object) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    spec = find_openclaw_official_provider_by_marker(normalized)
    if spec is None:
        spec = find_openclaw_official_provider_in_text(normalized)
    return spec.provider_name if spec else ""


def _collect_login_payload_provider_names(payload: object) -> set[str]:
    if isinstance(payload, dict):
        names: set[str] = set()
        for key, value in payload.items():
            if str(key or "").strip().lower() in _LOGIN_PROVIDER_SIGNAL_KEYS:
                provider_name = _official_provider_name_from_login_value(value)
                if provider_name:
                    names.add(provider_name)
            if isinstance(value, (dict, list)):
                names.update(_collect_login_payload_provider_names(value))
        return names
    if isinstance(payload, list):
        names: set[str] = set()
        for item in payload:
            names.update(_collect_login_payload_provider_names(item))
        return names
    return set()


def official_provider_names_from_login_state(config: dict[str, Any]) -> list[str]:
    provider_names: set[str] = set()
    auth = config.get("auth")
    if isinstance(auth, dict):
        provider_names.update(_collect_login_payload_provider_names(auth))

    plugins = config.get("plugins")
    if isinstance(plugins, dict):
        entries = plugins.get("entries")
        if isinstance(entries, dict):
            for plugin_name, payload in entries.items():
                if not _looks_like_login_plugin_entry(plugin_name, payload):
                    continue
                provider_name = _official_provider_name_from_login_value(plugin_name)
                if provider_name:
                    provider_names.add(provider_name)
                provider_names.update(_collect_login_payload_provider_names(payload))

    return [
        spec.provider_name
        for spec in OPENCLAW_OFFICIAL_PROVIDER_SPECS
        if spec.provider_name in provider_names
    ]


def prune_openclaw_login_state(config: dict[str, Any]) -> bool:
    changed = False
    if "auth" in config:
        config.pop("auth", None)
        changed = True

    plugins = config.get("plugins")
    if not isinstance(plugins, dict):
        return changed
    entries = plugins.get("entries")
    if not isinstance(entries, dict):
        return changed

    for plugin_name in list(entries):
        if _looks_like_login_plugin_entry(plugin_name, entries.get(plugin_name)):
            entries.pop(plugin_name, None)
            changed = True
    return changed


def ensure_official_provider_skeletons(config: dict[str, Any], provider_names: list[str]) -> bool:
    provider_names = [
        provider_name
        for provider_name in provider_names
        if provider_name in OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME
    ]
    if not provider_names:
        return False

    changed = False
    models = config.get("models")
    if not isinstance(models, dict):
        models = {}
        config["models"] = models
        changed = True
    if str(models.get("mode", "") or "").strip() != "merge":
        models["mode"] = "merge"
        changed = True

    providers = models.get("providers")
    if not isinstance(providers, dict):
        providers = {}
        models["providers"] = providers
        changed = True

    for provider_name in provider_names:
        spec = OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME[provider_name]
        provider = providers.get(provider_name)
        if not isinstance(provider, dict):
            provider = {}
            providers[provider_name] = provider
            changed = True
        if not str(provider.get("api", "") or "").strip():
            provider["api"] = spec.api
            changed = True
        if not normalize_http_url_candidate(str(provider.get("baseUrl", "") or "")):
            provider["baseUrl"] = spec.base_url
            changed = True
    return changed


def ensure_openclaw_provider_api_formats(config: dict[str, Any]) -> bool:
    providers = get_openclaw_providers(config)
    changed = False
    for provider_name, provider in providers.items():
        if not isinstance(provider, dict):
            continue
        if str(provider.get("api", "") or "").strip():
            continue
        api_format = api_format_from_openclaw_provider(provider, provider_name=str(provider_name))
        if not api_format:
            continue
        provider["api"] = api_format
        changed = True
    return changed


def materialize_official_provider_values(
    providers: dict[str, Any],
    *,
    auth_keys: dict[str, list[str]],
    process_env: dict[str, str],
) -> bool:
    changed = False
    for spec in OPENCLAW_OFFICIAL_PROVIDER_SPECS:
        provider_name = spec.provider_name
        provider = providers.get(provider_name)
        if not isinstance(provider, dict):
            continue
        api_key_val = str(provider.get("apiKey", "")).strip()
        if str(provider.get("api", "")).strip() != spec.api:
            continue

        key_items = collect_provider_api_key_items_by_priority(
            spec,
            api_key=api_key_val,
            auth_profile_values=auth_keys.get(provider_name, []),
            env=process_env,
        )
        real_key = str(key_items[0].get("value", "") or "").strip() if key_items else ""

        if real_key and provider.get("apiKey") != real_key:
            provider["apiKey"] = real_key
            changed = True
        base_url = normalize_http_url_candidate(str(provider.get("baseUrl", "")).strip())
        if not base_url:
            provider["baseUrl"] = spec.base_url
            changed = True
    return changed


__all__ = [
    "ensure_official_provider_skeletons",
    "ensure_openclaw_provider_api_formats",
    "materialize_official_provider_values",
    "official_provider_names_from_login_state",
    "prune_openclaw_login_state",
]
