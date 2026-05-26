from __future__ import annotations

from typing import Any

from packaging._shared.common.url_values import normalize_http_url_candidate
from packaging._shared.openclaw.official_providers import (
    OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME,
    find_openclaw_official_provider_by_marker,
)
from packaging.configure.env_values import usable_env_value


def ensure_auth_profile_providers(config: dict[str, Any], auth_keys: dict[str, list[str]]) -> bool:
    changed = False

    def ensure_provider_container() -> dict[str, Any]:
        nonlocal changed
        models = config.get("models")
        if not isinstance(models, dict):
            models = {}
            config["models"] = models
            changed = True
        providers = models.get("providers")
        if not isinstance(providers, dict):
            providers = {}
            models["providers"] = providers
            changed = True
        if not str(models.get("mode", "") or "").strip():
            models["mode"] = "merge"
            changed = True
        return providers

    for provider_name, values in auth_keys.items():
        if not values:
            continue
        providers = _get_providers(config)
        matched_provider_name = _match_existing_provider_name(provider_name, providers)
        if matched_provider_name:
            provider = providers.get(matched_provider_name)
            if not isinstance(provider, dict):
                continue
            if not usable_env_value(provider.get("apiKey", "")):
                provider["apiKey"] = values[0]
                changed = True
                models = config.get("models")
                if isinstance(models, dict) and not str(models.get("mode", "") or "").strip():
                    models["mode"] = "merge"
                    changed = True
            continue

        official_provider_name = _official_provider_name_from_auth_profile_name(provider_name)
        if official_provider_name:
            providers = ensure_provider_container()
            spec = OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME[official_provider_name]
            provider = providers.get(official_provider_name)
            if not isinstance(provider, dict):
                provider = {}
                providers[official_provider_name] = provider
                changed = True
            if provider.get("api") != spec.api:
                provider["api"] = spec.api
                changed = True
            if not usable_env_value(provider.get("apiKey", "")):
                provider["apiKey"] = values[0]
                changed = True
            if not normalize_http_url_candidate(str(provider.get("baseUrl", "") or "")):
                provider["baseUrl"] = spec.base_url
                changed = True
            continue
    return changed


def _get_providers(config: dict[str, Any]) -> dict[str, Any]:
    models = config.get("models")
    if not isinstance(models, dict):
        return {}
    providers = models.get("providers")
    return providers if isinstance(providers, dict) else {}


def _match_existing_provider_name(provider_name: str, providers: dict[str, Any]) -> str:
    normalized = str(provider_name or "").strip()
    if not normalized:
        return ""
    if normalized in providers:
        return normalized
    lowered = normalized.lower()
    matches = [name for name in providers if str(name).strip().lower() == lowered]
    return matches[0] if len(matches) == 1 else ""


def _official_provider_name_from_auth_profile_name(provider_name: str) -> str:
    spec = find_openclaw_official_provider_by_marker(provider_name)
    return spec.provider_name if spec else ""


__all__ = ["ensure_auth_profile_providers"]
