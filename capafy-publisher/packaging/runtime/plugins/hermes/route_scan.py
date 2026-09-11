from __future__ import annotations

from typing import Any, Optional

from packaging.common.url_values import normalize_http_url_candidate
from packaging.runtime.contracts import FieldLocation, LlmRoute, SourceKind
from packaging.runtime.contracts import build_llm_route
from packaging.runtime.plugins.hermes.provider import (
    HermesOfficialProviderSpec,
    find_hermes_official_provider_by_base_url,
    find_hermes_official_provider_by_key_reference,
    find_hermes_official_provider_by_marker,
    platform_api_format_from_block,
)


CONFIG_REL = ".hermes/config.yaml"
HERMES_DEFAULT_API_KEY_FIELD = "api_key"


def scan_current_hermes_route(config: dict[str, Any]) -> list[LlmRoute]:
    model_block = config.get("model")
    if not isinstance(model_block, dict):
        return []

    selected_block, group_path = _selected_provider_block(config, model_block)
    combined = dict(selected_block)
    combined.update({key: value for key, value in model_block.items() if key != "provider"})
    configured_url, configured_group_path, configured_url_field = _configured_url(
        model_block,
        selected_block,
        selected_group_path=group_path,
    )
    if configured_url:
        combined["base_url"] = configured_url
    spec = _official_spec(
        model_block,
        selected_block,
        route_block=combined,
        allow_key_hint=not bool(configured_url),
    )
    base_url = _base_url(combined, spec)
    if not base_url:
        return []

    provider_name = _provider_name(model_block, selected_block, spec)
    service = spec.service if spec is not None else provider_name or group_path
    model = str(
        model_block.get("default", "")
        or selected_block.get("default_model", "")
        or selected_block.get("model", "")
        or ""
    ).strip()
    location_group_path = configured_group_path or group_path
    url_field = configured_url_field or "base_url"
    location_path = _group_key_path(location_group_path, url_field)
    return [
        build_llm_route(
            service=service,
            group=f"{CONFIG_REL}#{group_path}",
            url=base_url,
            url_field=".".join(location_path),
            source_relpath=CONFIG_REL,
            source_kind=(
                SourceKind.FILE
                if configured_url
                else SourceKind.SYNTHESIZED
            ),
            location=FieldLocation(fmt="yaml", key_path=location_path),
            model=model,
            api_format=platform_api_format_from_block(combined, spec, model=model),
            provider_name=provider_name,
            api_key_field=HERMES_DEFAULT_API_KEY_FIELD,
        )
    ]


def _selected_provider_block(
    config: dict[str, Any],
    model_block: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    raw_provider = str(model_block.get("provider", "") or "").strip()
    custom_name = raw_provider.split(":", 1)[1].strip() if raw_provider.lower().startswith("custom:") else raw_provider
    providers = config.get("providers")
    if isinstance(providers, dict):
        for name, provider in providers.items():
            if not isinstance(provider, dict):
                continue
            if custom_name and str(name).strip().lower() == custom_name.lower():
                return provider, f"providers.{name}"
    custom_providers = config.get("custom_providers")
    if isinstance(custom_providers, list):
        for index, provider in enumerate(custom_providers):
            if not isinstance(provider, dict):
                continue
            name = str(provider.get("name", "") or "").strip()
            if custom_name and name.lower() == custom_name.lower():
                return provider, f"custom_providers[{index}]"
        if raw_provider.lower() == "custom" and len(custom_providers) == 1 and isinstance(custom_providers[0], dict):
            return custom_providers[0], "custom_providers[0]"
    return model_block, "model"


def _official_spec(
    model_block: dict[str, Any],
    selected_block: dict[str, Any],
    *,
    route_block: dict[str, Any],
    allow_key_hint: bool,
) -> Optional[HermesOfficialProviderSpec]:
    configured_url = _base_url_ref(route_block)
    if configured_url:
        spec = find_hermes_official_provider_by_base_url(configured_url)
        if spec is not None:
            return spec
    for value in (
        model_block.get("provider"),
        selected_block.get("provider"),
        selected_block.get("name"),
    ):
        spec = find_hermes_official_provider_by_marker(str(value or ""))
        if spec is not None:
            return spec
    if allow_key_hint:
        spec = find_hermes_official_provider_by_key_reference(
            _api_key_ref(route_block)
        )
        if spec is not None:
            return spec
    return None


def _base_url(
    block: dict[str, Any],
    spec: Optional[HermesOfficialProviderSpec],
) -> str:
    configured = normalize_http_url_candidate(_base_url_ref(block))
    if configured:
        return configured
    if spec is not None:
        return spec.base_url
    if str(block.get("provider", "") or "").strip().lower() == "openrouter":
        return "https://openrouter.ai/api/v1"
    return ""


def _provider_name(
    model_block: dict[str, Any],
    selected_block: dict[str, Any],
    spec: Optional[HermesOfficialProviderSpec],
) -> str:
    if spec is not None:
        return spec.provider_name
    for value in (selected_block.get("name"), model_block.get("provider")):
        normalized = str(value or "").strip()
        if normalized:
            return normalized.removeprefix("custom:")
    return ""


def _group_key_path(group_path: str, field: str) -> tuple[str, ...]:
    if group_path.startswith("custom_providers["):
        return (group_path, field)
    if group_path.startswith("providers."):
        return ("providers", group_path.removeprefix("providers."), field)
    return tuple([*group_path.split("."), field])


def _configured_url(
    model_block: dict[str, Any],
    selected_block: dict[str, Any],
    *,
    selected_group_path: str,
) -> tuple[str, str, str]:
    for block, group_path in ((model_block, "model"), (selected_block, selected_group_path)):
        for field in ("base_url", "api_base", "api", "url"):
            value = normalize_http_url_candidate(block.get(field, ""))
            if value:
                return value, group_path, field
    return "", "", ""


def _base_url_ref(block: dict[str, Any]) -> str:
    return str(
        block.get("base_url", "")
        or block.get("api_base", "")
        or block.get("api", "")
        or block.get("url", "")
        or ""
    )


def _api_key_ref(block: dict[str, Any]) -> object:
    return (
        block.get("api_key")
        or block.get("key_env")
        or block.get("api_key_env")
        or ""
    )


__all__ = ["CONFIG_REL", "scan_current_hermes_route"]
