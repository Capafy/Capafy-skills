from __future__ import annotations

from typing import Any

from packaging._shared.common.url_values import normalize_http_url_candidate
from packaging._shared.openclaw.official_providers import (
    OPENCLAW_OFFICIAL_PROVIDER_SPECS,
    OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME,
    OpenClawOfficialProviderSpec,
)
from packaging.configure.candidate import Candidate
from packaging.configure.contracts import FieldLocation, SourceKind
from packaging.configure.runtimes.openclaw.auth_profiles import load_auth_profile_keys
from packaging.configure.runtimes.openclaw.provider_keys import (
    collect_provider_api_key_items,
    dedupe_key_items,
    is_env_reference,
    real_value,
    resolve_api_key_config_value,
)
from packaging.configure.sensitive.literals import looks_like_platform_managed_placeholder_value
from packaging.configure.url_proxy.base import ScanContext


_CONFIG_REL = ".openclaw/openclaw.json"


def scan_openclaw_provider_candidates(ctx: ScanContext, config: dict[str, Any]) -> list[Candidate]:
    providers = get_openclaw_providers(config)
    if not providers:
        return []

    candidates: list[Candidate] = []

    for spec in OPENCLAW_OFFICIAL_PROVIDER_SPECS:
        provider_name = spec.provider_name
        provider = providers.get(provider_name)
        if not isinstance(provider, dict):
            continue
        provider_api_format = _api_format_from_openclaw_provider(provider)
        if provider_api_format != spec.api:
            continue

        api_key = str(provider.get("apiKey", "")).strip()
        base_url = str(provider.get("baseUrl", "")).strip()
        provider_model = model_id_from_openclaw_provider(provider)

        key_candidates = _official_provider_key_candidates(
            ctx,
            provider_name=provider_name,
            spec=spec,
            api_key=api_key,
        )
        key_candidates = [
            _candidate_with_provider_metadata(
                candidate,
                model=provider_model,
                api_format=provider_api_format,
            )
            for candidate in key_candidates
        ]
        if not key_candidates:
            key_candidates = [
                _placeholder_official_provider_key_candidate(
                    provider_name=provider_name,
                    spec=spec,
                    api_key=api_key,
                    model=provider_model,
                    api_format=provider_api_format,
                )
            ]

        candidates.extend(key_candidates)

        url_value = normalize_http_url_candidate(base_url)
        if not url_value:
            url_value = spec.base_url
        candidates.append(Candidate(
            role="base_url",
            field=f"models.providers.{provider_name}.baseUrl",
            value=url_value,
            source_kind=SourceKind.FILE,
            source_relpath=_CONFIG_REL,
            location=FieldLocation(
                fmt="json",
                json_pointer=f"/models/providers/{provider_name}/baseUrl",
            ),
            extra={
                "provider_name": provider_name,
                "service": spec.service,
                "model": provider_model,
                "api_format": provider_api_format,
            },
        ))

    official_names = set(OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME)
    for provider_name, provider in providers.items():
        if provider_name in official_names:
            continue
        if not isinstance(provider, dict):
            continue

        api_key = str(provider.get("apiKey", "")).strip()
        if not api_key or looks_like_platform_managed_placeholder_value(api_key):
            continue
        resolved_api_key = resolve_api_key_config_value(api_key, ctx.process_env)
        if not resolved_api_key:
            continue

        service = provider_name
        provider_model = model_id_from_openclaw_provider(provider)
        provider_api_format = _api_format_from_openclaw_provider(provider)
        candidates.append(Candidate(
            role="api_key",
            field=f"models.providers.{provider_name}.apiKey",
            value=resolved_api_key,
            source_kind=SourceKind.FILE,
            source_relpath=_CONFIG_REL,
            location=FieldLocation(
                fmt="json",
                json_pointer=f"/models/providers/{provider_name}/apiKey",
            ),
            extra={
                "provider_name": provider_name,
                "service": service,
                "model": provider_model,
                "api_format": provider_api_format,
            },
        ))

        base_url = str(provider.get("baseUrl", "")).strip()
        normalized_url = normalize_http_url_candidate(base_url)
        if normalized_url and not looks_like_platform_managed_placeholder_value(base_url):
            candidates.append(Candidate(
                role="base_url",
                field=f"models.providers.{provider_name}.baseUrl",
                value=normalized_url,
                source_kind=SourceKind.FILE,
                source_relpath=_CONFIG_REL,
                location=FieldLocation(
                    fmt="json",
                    json_pointer=f"/models/providers/{provider_name}/baseUrl",
                ),
                extra={
                    "provider_name": provider_name,
                    "service": service,
                    "model": provider_model,
                    "api_format": provider_api_format,
                },
            ))

    return candidates


def get_openclaw_providers(config: dict[str, Any]) -> dict[str, Any]:
    models = config.get("models")
    if not isinstance(models, dict):
        return {}
    providers = models.get("providers")
    return providers if isinstance(providers, dict) else {}


def model_id_from_openclaw_provider(provider: dict[str, Any]) -> str:
    models = provider.get("models")
    if not isinstance(models, list):
        return ""
    for item in models:
        if isinstance(item, dict):
            for key in ("id", "name", "model"):
                value = str(item.get(key, "") or "").strip()
                if value:
                    return value
        elif isinstance(item, str) and item.strip():
            return item.strip()
    return ""


def _api_format_from_openclaw_provider(provider: dict[str, Any]) -> str:
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


def _candidate_with_provider_metadata(candidate: Candidate, *, model: str, api_format: str) -> Candidate:
    extra = dict(candidate.extra)
    normalized_model = str(model or "").strip()
    normalized_api_format = str(api_format or "").strip()
    if normalized_model:
        extra["model"] = normalized_model
    if normalized_api_format:
        extra["api_format"] = normalized_api_format
    return Candidate(
        role=candidate.role,
        field=candidate.field,
        value=candidate.value,
        source_kind=candidate.source_kind,
        source_relpath=candidate.source_relpath,
        location=candidate.location,
        extra=extra,
    )


def _placeholder_official_provider_key_candidate(
    *,
    provider_name: str,
    spec: OpenClawOfficialProviderSpec,
    api_key: str,
    model: str,
    api_format: str,
) -> Candidate:
    return Candidate(
        role="api_key",
        field=f"models.providers.{provider_name}.apiKey",
        value="",
        source_kind=SourceKind.FILE,
        source_relpath=_CONFIG_REL,
        location=FieldLocation(
            fmt="json",
            json_pointer=f"/models/providers/{provider_name}/apiKey",
        ),
        extra={
            "provider_name": provider_name,
            "service": spec.service,
            "model": model,
            "api_format": api_format,
            "env_name": api_key if is_env_reference(api_key) else "",
            "placeholder_provider": True,
        },
    )


def _official_provider_key_candidates(
    ctx: ScanContext,
    *,
    provider_name: str,
    spec: OpenClawOfficialProviderSpec,
    api_key: str,
) -> list[Candidate]:
    key_items = collect_provider_api_key_items(spec, ctx.process_env)
    if not key_items:
        profile_values = load_auth_profile_keys(ctx).get(provider_name, [])
        key_items = [
            {"env_name": "", "value": value, "field_aliases": []}
            for value in profile_values
            if real_value(value)
        ]
    if not key_items:
        resolved = resolve_api_key_config_value(api_key, ctx.process_env)
        if resolved:
            key_items = [{"env_name": api_key if is_env_reference(api_key) else "", "value": resolved, "field_aliases": []}]

    result: list[Candidate] = []
    field = f"models.providers.{provider_name}.apiKey"
    for index, item in enumerate(dedupe_key_items(key_items)):
        value = str(item.get("value", "") or "").strip()
        if not value:
            continue
        result.append(Candidate(
            role="api_key",
            field=field,
            value=value,
            source_kind=SourceKind.FILE if index == 0 else SourceKind.PROCESS_ENV,
            source_relpath=_CONFIG_REL,
            location=FieldLocation(
                fmt="json",
                json_pointer=f"/models/providers/{provider_name}/apiKey",
            ) if index == 0 else None,
            extra={
                "provider_name": provider_name,
                "service": spec.service,
                "key_index": index,
                "env_name": str(item.get("env_name", "") or ""),
            },
        ))
    return result


__all__ = [
    "get_openclaw_providers",
    "model_id_from_openclaw_provider",
    "scan_openclaw_provider_candidates",
]
