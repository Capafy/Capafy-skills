from __future__ import annotations
from typing import Optional

from packaging.common.url_values import normalize_http_url_candidate
from packaging.runtime.llm.official_providers import (
    OfficialProviderSpec,
    build_platform_official_provider_specs,
    find_official_provider_by_base_url,
    find_official_provider_by_env_name,
    find_official_provider_by_marker,
    match_official_builtin_model_provider,
)
from packaging.runtime.plugins.support import env_reference_name


OpenClawOfficialProviderSpec = OfficialProviderSpec


def _sort_openclaw_official_specs(
    specs: tuple[OpenClawOfficialProviderSpec, ...],
) -> tuple[OpenClawOfficialProviderSpec, ...]:
    return tuple(
        sorted(
            specs,
            key=lambda spec: max((len(marker) for marker in spec.markers), default=0),
            reverse=True,
        )
    )


OPENCLAW_OFFICIAL_PROVIDER_SPECS = build_platform_official_provider_specs(
    "openclaw",
)
OPENCLAW_OFFICIAL_PROVIDER_SPECS = _sort_openclaw_official_specs(
    OPENCLAW_OFFICIAL_PROVIDER_SPECS
)

OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME = {
    spec.provider_name: spec
    for spec in OPENCLAW_OFFICIAL_PROVIDER_SPECS
}


def match_openclaw_builtin_model_provider(
    model_ref: str,
) -> Optional[tuple[OpenClawOfficialProviderSpec, str]]:
    return match_official_builtin_model_provider(
        model_ref,
        specs=OPENCLAW_OFFICIAL_PROVIDER_SPECS,
    )


def find_openclaw_official_provider_by_marker(
    value: str,
) -> Optional[OpenClawOfficialProviderSpec]:
    return find_official_provider_by_marker(
        value,
        specs=OPENCLAW_OFFICIAL_PROVIDER_SPECS,
        match_provider_identity=False,
    )


def find_openclaw_official_provider_by_base_url(
    value: str,
) -> Optional[OpenClawOfficialProviderSpec]:
    normalized = normalize_http_url_candidate(value).rstrip("/").lower()
    return find_official_provider_by_base_url(
        normalized,
        specs=OPENCLAW_OFFICIAL_PROVIDER_SPECS,
    )


def find_openclaw_official_provider_by_key_reference(
    value: object,
) -> Optional[OpenClawOfficialProviderSpec]:
    return find_official_provider_by_env_name(
        env_reference_name(value),
        platform="openclaw",
        specs=OPENCLAW_OFFICIAL_PROVIDER_SPECS,
    )


def find_openclaw_official_provider_in_text(
    value: str,
) -> Optional[OpenClawOfficialProviderSpec]:
    normalized = str(value or "").strip().lower()
    if not normalized or "oauth" in normalized:
        return None
    best_spec: Optional[OpenClawOfficialProviderSpec] = None
    best_marker_len = -1
    for spec in OPENCLAW_OFFICIAL_PROVIDER_SPECS:
        for marker in spec.markers:
            if marker in normalized and len(marker) > best_marker_len:
                best_spec = spec
                best_marker_len = len(marker)
    return best_spec


__all__ = [
    "OPENCLAW_OFFICIAL_PROVIDER_SPECS",
    "OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME",
    "OpenClawOfficialProviderSpec",
    "find_openclaw_official_provider_by_base_url",
    "find_openclaw_official_provider_by_marker",
    "find_openclaw_official_provider_by_key_reference",
    "find_openclaw_official_provider_in_text",
    "match_openclaw_builtin_model_provider",
]
