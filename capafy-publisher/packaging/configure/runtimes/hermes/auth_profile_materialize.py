from __future__ import annotations

from typing import Any, Optional

from packaging._shared.llm.official_providers import (
    ALL_OFFICIAL_PROVIDER_SPECS_BY_NAME,
    OfficialProviderSpec,
    find_official_provider_by_marker,
)
from packaging.configure.runtimes.hermes.api_modes import hermes_api_mode_from_url, hermes_default_api_mode
from packaging.configure.env_values import usable_env_value
from packaging.configure.runtimes.hermes.auth_profiles import HermesAuthProfileCredential
from packaging.configure.runtimes.hermes.provider_blocks import iter_hermes_provider_blocks
from packaging.configure.runtimes.hermes.provider_refs import custom_provider_name_map, find_custom_provider


def ensure_hermes_official_providers(
    config: dict[str, Any],
    oauth_keys: dict[str, list[str]],
    *,
    auth_credentials: Optional[dict[str, list[HermesAuthProfileCredential]]] = None,
) -> bool:
    changed = False
    for provider_block in iter_hermes_provider_blocks(config):
        if provider_block.is_custom:
            changed = _scrub_custom_provider(provider_block.block) or changed
            continue
        changed = _materialize_block(provider_block.block, oauth_keys, auth_credentials=auth_credentials) or changed
    changed = _ensure_oauth_custom_providers(config, oauth_keys, auth_credentials=auth_credentials) or changed
    return changed


def _materialize_block(
    block: dict[str, Any],
    oauth_keys: dict[str, list[str]],
    *,
    auth_credentials: Optional[dict[str, list[HermesAuthProfileCredential]]] = None,
) -> bool:
    spec = _resolve_official_spec(block)
    if spec is None:
        return False
    changed = False
    base_url = _credential_base_url(spec.provider_name, auth_credentials) or spec.base_url
    if block.get("base_url") != base_url:
        block["base_url"] = base_url
        changed = True
    if not usable_env_value(block.get("api_key")):
        keys = oauth_keys.get(spec.provider_name, [])
        if keys:
            block["api_key"] = keys[0]
            changed = True
            key_env = _credential_source_env(spec.provider_name, auth_credentials)
            if key_env and block.get("key_env") != key_env:
                block["key_env"] = key_env
                changed = True
    changed = _scrub_custom_provider(block) or changed
    return changed


def _scrub_custom_provider(block: dict[str, Any]) -> bool:
    changed = False
    for marker in ("auth_mode", "oauth_state", "subscription_proxy", "oauth_token"):
        if marker in block:
            block.pop(marker, None)
            changed = True
    return changed


def _ensure_oauth_custom_providers(
    config: dict[str, Any],
    oauth_keys: dict[str, list[str]],
    *,
    auth_credentials: Optional[dict[str, list[HermesAuthProfileCredential]]] = None,
) -> bool:
    if not _has_materializable_oauth_keys(oauth_keys):
        return False
    custom_providers = config.get("custom_providers")
    if custom_providers is not None and not isinstance(custom_providers, list):
        return False

    changed = False
    custom_groups = custom_provider_name_map(config)
    referenced_custom_names = _referenced_custom_provider_names(config)
    for provider_name, keys in oauth_keys.items():
        if not keys:
            continue
        if provider_name.lower().startswith("custom:"):
            custom_name = provider_name.split(":", 1)[1].strip()
            provider = find_custom_provider(custom_providers, custom_name)
            if isinstance(provider, dict) and not usable_env_value(provider.get("api_key")):
                provider["api_key"] = keys[0]
                changed = True
            continue
        spec = ALL_OFFICIAL_PROVIDER_SPECS_BY_NAME.get(provider_name)
        if spec is None:
            continue
        if provider_name.lower() in custom_groups:
            if not isinstance(custom_providers, list):
                continue
            provider = find_custom_provider(custom_providers, provider_name)
            if isinstance(provider, dict):
                changed = _materialize_custom_provider(
                    provider,
                    spec,
                    keys,
                    base_url=_credential_base_url(provider_name, auth_credentials),
                    key_env=_credential_source_env(provider_name, auth_credentials),
                    api_mode=_credential_api_mode(provider_name, spec, auth_credentials),
                ) or changed
            continue
        if provider_name.lower() in referenced_custom_names:
            if not isinstance(custom_providers, list):
                custom_providers = []
                config["custom_providers"] = custom_providers
            provider = {
                "name": provider_name,
                "base_url": _credential_base_url(provider_name, auth_credentials) or spec.base_url,
                "api_mode": _credential_api_mode(provider_name, spec, auth_credentials),
                "api_key": keys[0],
            }
            key_env = _credential_source_env(provider_name, auth_credentials)
            if key_env:
                provider["key_env"] = key_env
            custom_providers.append(provider)
            custom_groups[provider_name.lower()] = f"custom_providers[{len(custom_providers) - 1}]"
            changed = True
            continue
    return changed


def _has_materializable_oauth_keys(oauth_keys: dict[str, list[str]]) -> bool:
    for provider_name, keys in oauth_keys.items():
        if not keys:
            continue
        if str(provider_name or "").strip().lower().startswith("custom:"):
            return True
        if provider_name in ALL_OFFICIAL_PROVIDER_SPECS_BY_NAME:
            return True
    return False


def _referenced_custom_provider_names(config: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for provider_block in iter_hermes_provider_blocks(config):
        if provider_block.is_custom:
            continue
        raw_provider = str(provider_block.block.get("provider", "") or "").strip()
        if not raw_provider:
            continue
        if raw_provider.lower().startswith("custom:"):
            raw_provider = raw_provider.split(":", 1)[1].strip()
        if raw_provider:
            names.add(raw_provider.lower())
    return names


def _materialize_custom_provider(
    provider: dict[str, Any],
    spec: OfficialProviderSpec,
    keys: list[str],
    *,
    base_url: str = "",
    key_env: str = "",
    api_mode: str = "",
) -> bool:
    changed = _scrub_custom_provider(provider)
    resolved_base_url = base_url or spec.base_url
    if provider.get("base_url") != resolved_base_url:
        provider["base_url"] = resolved_base_url
        changed = True
    resolved_api_mode = api_mode or hermes_api_mode_from_url(resolved_base_url) or hermes_default_api_mode(spec)
    if provider.get("api_mode") != resolved_api_mode:
        provider["api_mode"] = resolved_api_mode
        changed = True
    if keys and not usable_env_value(provider.get("api_key")):
        provider["api_key"] = keys[0]
        changed = True
    if key_env and provider.get("key_env") != key_env:
        provider["key_env"] = key_env
        changed = True
    return changed


def _resolve_official_spec(block: dict[str, Any]) -> Optional[OfficialProviderSpec]:
    provider = _canonical_provider_marker(str(block.get("provider", "") or "").strip())
    if provider in ALL_OFFICIAL_PROVIDER_SPECS_BY_NAME:
        return ALL_OFFICIAL_PROVIDER_SPECS_BY_NAME[provider]
    return find_official_provider_by_marker(provider)


def _credential_base_url(
    provider_name: str,
    credentials: Optional[dict[str, list[HermesAuthProfileCredential]]],
) -> str:
    if not credentials:
        return ""
    for credential in credentials.get(provider_name, []):
        if credential.base_url:
            return credential.base_url
    return ""


def _credential_source_env(
    provider_name: str,
    credentials: Optional[dict[str, list[HermesAuthProfileCredential]]],
) -> str:
    if not credentials:
        return ""
    for credential in credentials.get(provider_name, []):
        if credential.source_env:
            return credential.source_env
    return ""


def _credential_api_mode(
    provider_name: str,
    spec: OfficialProviderSpec,
    credentials: Optional[dict[str, list[HermesAuthProfileCredential]]],
) -> str:
    if credentials:
        for credential in credentials.get(provider_name, []):
            if credential.api_mode:
                return credential.api_mode
    return hermes_api_mode_from_url(_credential_base_url(provider_name, credentials)) or hermes_default_api_mode(spec)


def _canonical_provider_marker(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "minimax-cn":
        return "minimax"
    return normalized


__all__ = ["ensure_hermes_official_providers"]
