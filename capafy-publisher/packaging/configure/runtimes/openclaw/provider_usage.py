from __future__ import annotations

from typing import Any, Optional

from packaging._shared.common.url_values import normalize_http_url_candidate
from packaging._shared.openclaw.official_providers import (
    OPENCLAW_OFFICIAL_PROVIDER_SPECS,
    OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME,
    OpenClawOfficialProviderSpec,
    find_openclaw_official_provider_in_text,
    match_openclaw_builtin_model_provider,
)


def get_openclaw_providers(config: dict[str, Any]) -> dict[str, Any]:
    models = config.get("models")
    if not isinstance(models, dict):
        return {}
    providers = models.get("providers")
    return providers if isinstance(providers, dict) else {}


def provider_from_openclaw_model_ref(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().split("/", 1)[0].strip()


def openclaw_model_id_from_entry(entry: object) -> str:
    if isinstance(entry, str):
        return entry.strip()
    if not isinstance(entry, dict):
        return ""
    for key in ("id", "name", "model"):
        value = str(entry.get(key, "") or "").strip()
        if value:
            return value
    return ""


def model_id_from_openclaw_provider(provider: dict[str, Any]) -> str:
    for model_ref in iter_openclaw_provider_model_refs(provider):
        return model_ref
    return ""


def iter_openclaw_provider_model_refs(provider: dict[str, Any]) -> list[str]:
    models = provider.get("models")
    if not isinstance(models, list):
        return []
    refs: list[str] = []
    for item in models:
        value = openclaw_model_id_from_entry(item)
        if value:
            refs.append(value)
    return refs


def _api_format_from_provider_models(provider: dict[str, Any]) -> str:
    api_format = str(provider.get("api", "") or "").strip()
    if api_format:
        return api_format
    models = provider.get("models")
    if not isinstance(models, list):
        return ""
    for item in models:
        if not isinstance(item, dict):
            continue
        api_format = str(item.get("api", "") or "").strip()
        if api_format:
            return api_format
    return ""


def _official_spec_from_base_url(base_url: str) -> Optional[OpenClawOfficialProviderSpec]:
    normalized = normalize_http_url_candidate(base_url).rstrip("/").lower()
    if not normalized:
        return None
    for spec in OPENCLAW_OFFICIAL_PROVIDER_SPECS:
        if normalize_http_url_candidate(spec.base_url).rstrip("/").lower() == normalized:
            return spec
    return None


def api_format_from_openclaw_provider(provider: dict[str, Any], *, provider_name: str = "") -> str:
    api_format = _api_format_from_provider_models(provider)
    if api_format:
        return api_format

    spec = OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME.get(provider_name)
    if spec is not None:
        return spec.api

    spec = _official_spec_from_base_url(str(provider.get("baseUrl", "") or ""))
    if spec is not None:
        return spec.api

    for model_ref in iter_openclaw_provider_model_refs(provider):
        matched = match_openclaw_builtin_model_provider(model_ref)
        if matched is not None:
            spec, _model_name = matched
            return spec.api

    spec = find_openclaw_official_provider_in_text(provider_name)
    if spec is not None:
        return spec.api
    return ""


def path_likely_contains_openclaw_model_ref(path_parts: tuple[str, ...]) -> bool:
    lowered = [part.lower() for part in path_parts]
    if lowered and lowered[0] == "env":
        return False
    if "memorysearch" in lowered:
        return False
    return any("model" in part or "fallback" in part for part in lowered)


def iter_openclaw_model_ref_values(node: object, path_parts: tuple[str, ...] = ()) -> list[str]:
    lowered = tuple(part.lower() for part in path_parts)
    if len(lowered) >= 2 and lowered[:2] == ("models", "providers"):
        return []
    if isinstance(node, dict):
        values = []
        for key, value in node.items():
            if path_likely_contains_openclaw_model_ref((*path_parts, str(key))):
                values.append(str(key))
            values.extend(iter_openclaw_model_ref_values(value, (*path_parts, str(key))))
        return values
    if isinstance(node, list):
        values = []
        for index, value in enumerate(node):
            values.extend(iter_openclaw_model_ref_values(value, (*path_parts, str(index))))
        return values
    if isinstance(node, str) and path_likely_contains_openclaw_model_ref(path_parts):
        return [node]
    return []


def used_openclaw_provider_names(config: dict[str, Any]) -> set[str]:
    providers = set(get_openclaw_providers(config))
    if not providers:
        return set()
    return {
        provider
        for provider in (
            provider_from_openclaw_model_ref(value)
            for value in iter_openclaw_model_ref_values(config)
        )
        if provider in providers
    }


def selected_openclaw_provider_names(config: dict[str, Any]) -> set[str]:
    providers = get_openclaw_providers(config)
    if not providers:
        return set()
    used = used_openclaw_provider_names(config)
    if used:
        return used
    if len(providers) == 1:
        return {str(provider_name) for provider_name in providers}
    return set()


def builtin_openclaw_provider_map(provider_names: set[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for provider_name in provider_names:
        spec = OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME.get(provider_name)
        if spec is None:
            continue
        for prefix in spec.model_prefixes:
            builtin_provider = prefix.rstrip("/")
            if builtin_provider:
                result[builtin_provider] = provider_name
        for marker in spec.markers:
            if marker:
                result[marker] = provider_name
    return result


__all__ = [
    "api_format_from_openclaw_provider",
    "builtin_openclaw_provider_map",
    "get_openclaw_providers",
    "iter_openclaw_model_ref_values",
    "iter_openclaw_provider_model_refs",
    "model_id_from_openclaw_provider",
    "openclaw_model_id_from_entry",
    "path_likely_contains_openclaw_model_ref",
    "provider_from_openclaw_model_ref",
    "selected_openclaw_provider_names",
    "used_openclaw_provider_names",
]
