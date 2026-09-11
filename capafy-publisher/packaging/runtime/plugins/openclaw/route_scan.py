from __future__ import annotations

import re
from typing import Any, Mapping, Optional

from packaging.common.url_values import normalize_http_url_candidate
from packaging.runtime.contracts import FieldLocation, LlmRoute, SourceKind
from packaging.runtime.contracts import build_llm_route
from packaging.runtime.plugins.openclaw.official_providers import (
    OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME,
    OpenClawOfficialProviderSpec,
    find_openclaw_official_provider_by_base_url,
    find_openclaw_official_provider_in_text,
    find_openclaw_official_provider_by_key_reference,
    find_openclaw_official_provider_by_marker,
    match_openclaw_builtin_model_provider,
)


OPENCLAW_CONFIG_REL = ".openclaw/openclaw.json"
OPENCLAW_MAIN_MODELS_REL = ".openclaw/agents/main/agent/models.json"
OPENCLAW_DEFAULT_API_KEY_FIELD = "apiKey"
_ENV_REFERENCE_RE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


def scan_current_openclaw_route(
    config: dict[str, Any],
    *,
    models_payload: Optional[dict[str, Any]] = None,
    process_env: Optional[Mapping[str, str]] = None,
) -> list[LlmRoute]:
    model_ref = _selected_model_ref(config)
    model_ref = _resolve_model_ref(model_ref, config=config, process_env=process_env or {})
    if not model_ref:
        return []

    configured_providers = _provider_sources(config, models_payload)
    provider_name, model, spec = _resolve_provider_and_model(model_ref, configured_providers)
    if not provider_name or not model:
        return []

    provider, source_relpath = configured_providers.get(provider_name, ({}, OPENCLAW_CONFIG_REL))
    if not isinstance(provider, dict):
        provider = {}
    configured_url = normalize_http_url_candidate(provider.get("baseUrl", ""))
    if spec is None:
        spec = _official_spec(
            provider_name,
            provider,
            allow_key_hint=not bool(configured_url),
        )

    base_url = configured_url or (spec.base_url if spec is not None else "")
    api_format = _provider_api_format(provider, provider_name=provider_name)
    if not api_format and spec is not None:
        api_format = spec.api
    if not base_url or not api_format:
        return []

    route_provider_name = spec.provider_name if spec is not None else provider_name
    service = spec.service if spec is not None else provider_name
    pointer_prefix = "/providers" if source_relpath == OPENCLAW_MAIN_MODELS_REL else "/models/providers"
    return [
        build_llm_route(
            service=service,
            group=f"{source_relpath}#models.providers.{route_provider_name}",
            url=base_url,
            url_field=f"models.providers.{route_provider_name}.baseUrl",
            source_relpath=source_relpath,
            source_kind=SourceKind.FILE if configured_url else SourceKind.SYNTHESIZED,
            location=FieldLocation(
                fmt="json",
                json_pointer=f"{pointer_prefix}/{_escape_json_pointer(provider_name)}/baseUrl",
            ),
            model=model,
            api_format=api_format,
            provider_name=route_provider_name,
            api_key_field=OPENCLAW_DEFAULT_API_KEY_FIELD,
        )
    ]


def selected_model_environment_name(config: dict[str, Any]) -> str:
    match = _ENV_REFERENCE_RE.fullmatch(_selected_model_ref(config))
    return match.group(1) if match is not None else ""


def _selected_model_ref(config: dict[str, Any]) -> str:
    agents = config.get("agents")
    if isinstance(agents, dict):
        defaults = agents.get("defaults")
        if isinstance(defaults, dict):
            selected = _model_value(defaults.get("model"))
            if selected:
                return selected
    return _model_value(config.get("model"))


def _model_value(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, dict):
        return ""
    return str(value.get("primary", "") or value.get("model", "") or "").strip()


def _resolve_model_ref(
    value: str,
    *,
    config: dict[str, Any],
    process_env: Mapping[str, str],
) -> str:
    match = _ENV_REFERENCE_RE.fullmatch(value)
    if match is None:
        return value
    name = match.group(1)
    config_env = config.get("env")
    if isinstance(config_env, dict):
        configured = str(config_env.get(name, "") or "").strip()
        if configured:
            return configured
    return str(process_env.get(name, "") or "").strip()


def _provider_sources(
    config: dict[str, Any],
    models_payload: Optional[dict[str, Any]],
) -> dict[str, tuple[dict[str, Any], str]]:
    result: dict[str, tuple[dict[str, Any], str]] = {}
    models = config.get("models")
    providers = models.get("providers") if isinstance(models, dict) else None
    if isinstance(providers, dict):
        for name, provider in providers.items():
            if isinstance(provider, dict):
                result[str(name)] = (provider, OPENCLAW_CONFIG_REL)
    models_providers = models_payload.get("providers") if isinstance(models_payload, dict) else None
    if isinstance(models_providers, dict):
        for name, provider in models_providers.items():
            if isinstance(provider, dict):
                result.setdefault(str(name), (provider, OPENCLAW_MAIN_MODELS_REL))
    return result


def _provider_api_format(provider: dict[str, Any], *, provider_name: str) -> str:
    api_format = str(provider.get("api", "") or "").strip()
    models = provider.get("models")
    if not api_format and isinstance(models, list):
        for item in models:
            if not isinstance(item, dict):
                continue
            api_format = str(item.get("api", "") or "").strip()
            if api_format:
                break
    if api_format:
        return api_format

    spec = OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME.get(provider_name)
    if spec is None:
        spec = find_openclaw_official_provider_by_base_url(
            str(provider.get("baseUrl", "") or "")
        )
    if spec is not None:
        return spec.api

    if isinstance(models, list):
        for item in models:
            model_ref = _provider_model_ref(item)
            matched = match_openclaw_builtin_model_provider(model_ref) if model_ref else None
            if matched is not None:
                spec, _model_name = matched
                return spec.api

    spec = find_openclaw_official_provider_in_text(provider_name)
    return spec.api if spec is not None else ""


def _provider_model_ref(entry: object) -> str:
    if isinstance(entry, str):
        return entry.strip()
    if not isinstance(entry, dict):
        return ""
    for key in ("id", "name", "model"):
        value = str(entry.get(key, "") or "").strip()
        if value:
            return value
    return ""


def _resolve_provider_and_model(
    model_ref: str,
    providers: dict[str, tuple[dict[str, Any], str]],
) -> tuple[str, str, Optional[OpenClawOfficialProviderSpec]]:
    if "/" in model_ref:
        provider_name, model = (part.strip() for part in model_ref.split("/", 1))
        if provider_name in providers:
            return provider_name, model, None
    matched = match_openclaw_builtin_model_provider(model_ref)
    if matched is not None:
        spec, model = matched
        return spec.provider_name, model, spec
    return "", "", None


def _official_spec(
    provider_name: str,
    provider: dict[str, Any],
    *,
    allow_key_hint: bool,
) -> Optional[OpenClawOfficialProviderSpec]:
    spec = find_openclaw_official_provider_by_base_url(str(provider.get("baseUrl", "") or ""))
    if spec is not None:
        return spec
    spec = OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME.get(provider_name)
    if spec is not None:
        return spec
    spec = find_openclaw_official_provider_by_marker(provider_name)
    if spec is not None:
        return spec
    if allow_key_hint:
        spec = find_openclaw_official_provider_by_key_reference(provider.get("apiKey"))
        if spec is not None:
            return spec
    return None


def _escape_json_pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


__all__ = [
    "OPENCLAW_CONFIG_REL",
    "OPENCLAW_MAIN_MODELS_REL",
    "scan_current_openclaw_route",
    "selected_model_environment_name",
]
