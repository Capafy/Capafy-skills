from __future__ import annotations

from typing import Any, Optional

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
    collect_provider_api_key_items_by_priority,
    dedupe_key_items,
)
from packaging.configure.env_values import (
    env_reference_name,
    resolve_env_reference_or_value,
)
from packaging.configure.runtimes.openclaw.provider_usage import (
    api_format_from_openclaw_provider,
    get_openclaw_providers,
    model_id_from_openclaw_provider,
    selected_openclaw_provider_names,
)
from packaging.configure.sensitive.literals import looks_like_platform_managed_placeholder_value
from packaging.configure.url_proxy.base import ScanContext


_CONFIG_REL = ".openclaw/openclaw.json"


def scan_openclaw_provider_candidates(ctx: ScanContext, config: dict[str, Any]) -> list[Candidate]:
    providers = get_openclaw_providers(config)
    if not providers:
        return []
    selected_providers = selected_openclaw_provider_names(config)

    candidates: list[Candidate] = []

    for spec in OPENCLAW_OFFICIAL_PROVIDER_SPECS:
        provider_name = spec.provider_name
        if provider_name not in selected_providers:
            continue
        provider = providers.get(provider_name)
        if not isinstance(provider, dict):
            continue
        provider_api_format = api_format_from_openclaw_provider(provider, provider_name=provider_name)
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
            model=provider_model,
            api_format=provider_api_format,
        )
        if not key_candidates:
            key_candidates = [
                _placeholder_provider_key_candidate(
                    provider_name=provider_name,
                    service=spec.service,
                    api_key=api_key,
                    model=provider_model,
                    api_format=provider_api_format,
                )
            ]

        candidates.extend(key_candidates)

        url_value = normalize_http_url_candidate(base_url)
        if not url_value:
            url_value = spec.base_url
        candidates.append(_base_url_candidate(
            provider_name=provider_name,
            service=spec.service,
            value=url_value,
            model=provider_model,
            api_format=provider_api_format,
        ))

    official_names = set(OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME)
    for provider_name, provider in providers.items():
        if provider_name in official_names:
            continue
        if provider_name not in selected_providers:
            continue
        if not isinstance(provider, dict):
            continue

        service = provider_name
        provider_model = model_id_from_openclaw_provider(provider)
        provider_api_format = api_format_from_openclaw_provider(provider, provider_name=provider_name)
        base_url = str(provider.get("baseUrl", "")).strip()
        normalized_url = normalize_http_url_candidate(base_url)

        api_key = str(provider.get("apiKey", "")).strip()
        resolved_api_key = resolve_env_reference_or_value(api_key, ctx.process_env)
        if resolved_api_key:
            candidates.append(_api_key_candidate(
                provider_name=provider_name,
                service=service,
                value=resolved_api_key,
                model=provider_model,
                api_format=provider_api_format,
            ))
        elif normalized_url and not looks_like_platform_managed_placeholder_value(base_url):
            candidates.append(_placeholder_provider_key_candidate(
                provider_name=provider_name,
                service=service,
                api_key=api_key,
                model=provider_model,
                api_format=provider_api_format,
            ))

        if normalized_url and not looks_like_platform_managed_placeholder_value(base_url):
            candidates.append(_base_url_candidate(
                provider_name=provider_name,
                service=service,
                value=normalized_url,
                model=provider_model,
                api_format=provider_api_format,
            ))

    return candidates


def _provider_json_location(provider_name: str, field_name: str) -> FieldLocation:
    return FieldLocation(
        fmt="json",
        json_pointer=f"/models/providers/{provider_name}/{field_name}",
    )


def _provider_extra(
    *,
    provider_name: str,
    service: str,
    model: str,
    api_format: str,
    extra: Optional[dict[str, object]] = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "provider_name": provider_name,
        "service": service,
        "model": model,
        "api_format": api_format,
    }
    if extra:
        result.update(extra)
    return result


def _api_key_candidate(
    *,
    provider_name: str,
    service: str,
    value: str,
    model: str,
    api_format: str,
    source_kind: SourceKind = SourceKind.FILE,
    key_index: Optional[int] = None,
    env_name: str = "",
    extra: Optional[dict[str, object]] = None,
) -> Candidate:
    key_extra: dict[str, object] = {"env_name": env_name}
    if key_index is not None:
        key_extra["key_index"] = key_index
    if extra:
        key_extra.update(extra)
    return Candidate(
        role="api_key",
        field=f"models.providers.{provider_name}.apiKey",
        value=value,
        source_kind=source_kind,
        source_relpath=_CONFIG_REL,
        location=_provider_json_location(provider_name, "apiKey") if source_kind == SourceKind.FILE else None,
        extra=_provider_extra(
            provider_name=provider_name,
            service=service,
            model=model,
            api_format=api_format,
            extra=key_extra,
        ),
    )


def _placeholder_provider_key_candidate(
    *,
    provider_name: str,
    service: str,
    api_key: str,
    model: str,
    api_format: str,
) -> Candidate:
    return _api_key_candidate(
        provider_name=provider_name,
        service=service,
        value="",
        model=model,
        api_format=api_format,
        env_name=env_reference_name(api_key),
        extra={"placeholder_provider": True},
    )


def _base_url_candidate(
    *,
    provider_name: str,
    service: str,
    value: str,
    model: str,
    api_format: str,
) -> Candidate:
    return Candidate(
        role="base_url",
        field=f"models.providers.{provider_name}.baseUrl",
        value=value,
        source_kind=SourceKind.FILE,
        source_relpath=_CONFIG_REL,
        location=_provider_json_location(provider_name, "baseUrl"),
        extra=_provider_extra(
            provider_name=provider_name,
            service=service,
            model=model,
            api_format=api_format,
        ),
    )


def _official_provider_key_candidates(
    ctx: ScanContext,
    *,
    provider_name: str,
    spec: OpenClawOfficialProviderSpec,
    api_key: str,
    model: str,
    api_format: str,
) -> list[Candidate]:
    key_items = collect_provider_api_key_items_by_priority(
        spec,
        api_key=api_key,
        auth_profile_values=load_auth_profile_keys(ctx).get(provider_name, []),
        env=ctx.process_env,
    )

    result: list[Candidate] = []
    for index, item in enumerate(dedupe_key_items(key_items)):
        value = str(item.get("value", "") or "").strip()
        if not value:
            continue
        result.append(_api_key_candidate(
            provider_name=provider_name,
            service=spec.service,
            value=value,
            model=model,
            api_format=api_format,
            source_kind=SourceKind.FILE if index == 0 else SourceKind.PROCESS_ENV,
            key_index=index,
            env_name=str(item.get("env_name", "") or ""),
        ))
    return result


__all__ = ["scan_openclaw_provider_candidates"]
