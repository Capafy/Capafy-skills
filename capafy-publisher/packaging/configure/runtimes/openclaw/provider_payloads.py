from __future__ import annotations

from typing import Optional

from packaging._shared.config_files.json_io import clone_json_value
from packaging._shared.common.url_values import normalize_http_url_candidate
from packaging.configure.runtimes.openclaw.official_providers import (
    OpenClawOfficialProviderSpec,
    find_openclaw_official_provider_by_marker,
)
from packaging.configure.runtimes.openclaw.provider_env_templates import OPENCLAW_CONFIG_REL_SOURCE
from packaging.configure.runtimes.openclaw.provider_usage import openclaw_model_id_from_entry
from packaging.configure.sensitive.literals import looks_like_platform_managed_placeholder_value
from packaging.configure.sensitive.placeholders import build_placeholder


_DEFAULT_MODEL_TEMPLATE = {
    "reasoning": True,
    "input": ["text", "image"],
    "cost": {
        "input": 0,
        "output": 0,
        "cacheRead": 0,
        "cacheWrite": 0,
    },
    "contextWindow": 200000,
    "maxTokens": 64000,
    "headers": {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json",
    },
}


def official_provider_placeholder(
    spec: OpenClawOfficialProviderSpec,
    provider_name: str,
    *,
    field: str,
    value_type: str = "",
) -> str:
    return build_placeholder(
        spec.service,
        OPENCLAW_CONFIG_REL_SOURCE,
        field=f"models.providers.{provider_name}.{field}",
        locator=spec.base_url,
        value_type=value_type,
    )


def discover_model_template(payload: dict[str, object]) -> Optional[dict[str, object]]:
    models = payload.get("models")
    if not isinstance(models, dict):
        return None
    providers = models.get("providers")
    if not isinstance(providers, dict):
        return None
    for provider_payload in providers.values():
        if not isinstance(provider_payload, dict):
            continue
        model_entries = provider_payload.get("models")
        if not isinstance(model_entries, list) or not model_entries:
            continue
        first_entry = model_entries[0]
        if isinstance(first_entry, dict):
            return clone_json_value(first_entry)
    return None


def _build_model_entry(model_name: str, template: Optional[dict[str, object]]) -> dict[str, object]:
    entry_template = (
        clone_json_value(template)
        if isinstance(template, dict)
        else clone_json_value(_DEFAULT_MODEL_TEMPLATE)
    )
    if not isinstance(entry_template, dict):
        entry_template = clone_json_value(_DEFAULT_MODEL_TEMPLATE)
    entry_template["id"] = model_name
    entry_template["name"] = model_name
    return entry_template


def provider_name_for_spec(
    spec: OpenClawOfficialProviderSpec,
    providers: dict[str, object],
    assigned_names: dict[str, str],
) -> str:
    family = spec.family
    if family in assigned_names:
        return assigned_names[family]

    if isinstance(providers.get(spec.provider_name), dict):
        assigned_names[family] = spec.provider_name
        return spec.provider_name

    candidate = spec.provider_name
    suffix = 2
    while True:
        existing = providers.get(candidate)
        if not isinstance(existing, dict):
            assigned_names[family] = candidate
            return candidate
        if provider_payload_matches_spec(existing, spec, provider_name=candidate):
            assigned_names[family] = candidate
            return candidate
        candidate = f"{spec.provider_name}_{suffix}"
        suffix += 1


def _provider_alias_matches_spec(
    provider_name: str,
    payload: dict[str, object],
) -> Optional[OpenClawOfficialProviderSpec]:
    spec = find_openclaw_official_provider_by_marker(provider_name)
    if spec is None:
        return None
    api = str(payload.get("api", "") or "").strip()
    if api and api != spec.api:
        return None
    return spec


def _merge_provider_models(target: dict[str, object], source: dict[str, object]) -> bool:
    source_models = source.get("models")
    if not isinstance(source_models, list):
        return False
    target_models = target.get("models")
    if not isinstance(target_models, list):
        target_models = []
        target["models"] = target_models
    seen = {
        key
        for key in (openclaw_model_id_from_entry(item) for item in target_models)
        if key
    }
    changed = False
    for item in source_models:
        key = openclaw_model_id_from_entry(item)
        if key and key in seen:
            continue
        target_models.append(clone_json_value(item))
        if key:
            seen.add(key)
        changed = True
    return changed


def _merge_official_provider_alias(
    target: dict[str, object],
    source: dict[str, object],
    spec: OpenClawOfficialProviderSpec,
) -> bool:
    changed = False
    for key, value in source.items():
        if key in {"api", "apiKey", "baseUrl", "models"}:
            continue
        if key not in target:
            target[key] = clone_json_value(value)
            changed = True

    source_key = str(source.get("apiKey", "") or "").strip()
    target_key = str(target.get("apiKey", "") or "").strip()
    if source_key and (not target_key or looks_like_platform_managed_placeholder_value(target_key)):
        target["apiKey"] = source_key
        changed = True

    source_url = str(source.get("baseUrl", "") or "").strip()
    target_url = str(target.get("baseUrl", "") or "").strip()
    if source_url and (
        not target_url
        or looks_like_platform_managed_placeholder_value(target_url)
        or not normalize_http_url_candidate(target_url)
    ):
        target["baseUrl"] = source_url
        changed = True

    changed = _merge_provider_models(target, source) or changed
    if target.get("api") != spec.api:
        target["api"] = spec.api
        changed = True
    return changed


def canonicalize_official_provider_aliases(providers: dict[str, object]) -> int:
    rewrites = 0
    for provider_name in list(providers):
        provider = providers.get(provider_name)
        if not isinstance(provider, dict):
            continue
        spec = _provider_alias_matches_spec(provider_name, provider)
        if spec is None:
            continue

        canonical_name = spec.provider_name
        canonical_provider = providers.get(canonical_name)
        if not isinstance(canonical_provider, dict):
            providers[canonical_name] = provider
            providers.pop(provider_name, None)
            if provider.get("api") != spec.api:
                provider["api"] = spec.api
            rewrites += 1
            continue

        if _merge_official_provider_alias(canonical_provider, provider, spec):
            rewrites += 1
        providers.pop(provider_name, None)
        rewrites += 1
    return rewrites


def provider_payload_matches_spec(
    payload: dict[str, object],
    spec: OpenClawOfficialProviderSpec,
    *,
    provider_name: str,
) -> bool:
    if str(payload.get("api", "")).strip() != spec.api:
        return False

    api_key = str(payload.get("apiKey", "") or "").strip()
    accepted_keys = {
        spec.default_env_key,
        official_provider_placeholder(spec, provider_name, field="apiKey"),
    }
    accepted_keys.update(item for item in spec.exact_env_keys if item)
    key_matches = (
        not api_key
        or api_key in accepted_keys
        or looks_like_platform_managed_placeholder_value(api_key)
    )

    base_url = str(payload.get("baseUrl", "") or "").strip()
    accepted_urls = {
        spec.base_url,
        official_provider_placeholder(spec, provider_name, field="baseUrl", value_type="url"),
    }
    url_matches = (
        not base_url
        or base_url in accepted_urls
        or looks_like_platform_managed_placeholder_value(base_url)
    )
    return key_matches and url_matches


def ensure_provider_payload(
    providers: dict[str, object],
    provider_name: str,
    *,
    spec: OpenClawOfficialProviderSpec,
    model_name: str,
    model_template: Optional[dict[str, object]],
) -> None:
    provider_payload = providers.get(provider_name)
    if not isinstance(provider_payload, dict):
        provider_payload = {}
        providers[provider_name] = provider_payload

    provider_payload["api"] = spec.api
    api_key = str(provider_payload.get("apiKey", "") or "").strip()
    if not api_key or looks_like_platform_managed_placeholder_value(api_key):
        provider_payload["apiKey"] = official_provider_placeholder(spec, provider_name, field="apiKey")
    base_url = str(provider_payload.get("baseUrl", "") or "").strip()
    if (
        not base_url
        or looks_like_platform_managed_placeholder_value(base_url)
        or not normalize_http_url_candidate(base_url)
    ):
        provider_payload["baseUrl"] = official_provider_placeholder(
            spec,
            provider_name,
            field="baseUrl",
            value_type="url",
        )

    model_entries = provider_payload.get("models")
    if not isinstance(model_entries, list):
        model_entries = []
        provider_payload["models"] = model_entries

    if any(isinstance(item, dict) and str(item.get("id", "")).strip() == model_name for item in model_entries):
        return
    model_entries.append(_build_model_entry(model_name, model_template))


__all__ = [
    "canonicalize_official_provider_aliases",
    "discover_model_template",
    "ensure_provider_payload",
    "official_provider_placeholder",
    "provider_name_for_spec",
    "provider_payload_matches_spec",
]
