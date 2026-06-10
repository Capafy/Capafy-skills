from __future__ import annotations
from typing import Optional

from packaging._shared.llm.official_providers import (
    ALL_OFFICIAL_PROVIDER_SPECS,
    OfficialProviderSpec as OpenClawOfficialProviderSpec,
    find_official_provider_by_marker,
    find_official_provider_in_text,
    match_official_builtin_model_provider,
)


OPENCLAW_OFFICIAL_PROVIDER_SPECS = tuple(
    spec for spec in ALL_OFFICIAL_PROVIDER_SPECS
    if spec.family in {"openai", "anthropic", "google"}
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


def find_openclaw_official_provider_in_text(
    value: str,
) -> Optional[OpenClawOfficialProviderSpec]:
    return find_official_provider_in_text(
        value,
        specs=OPENCLAW_OFFICIAL_PROVIDER_SPECS,
        match_provider_identity=False,
    )


__all__ = [
    "OPENCLAW_OFFICIAL_PROVIDER_SPECS",
    "OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME",
    "OpenClawOfficialProviderSpec",
    "find_openclaw_official_provider_by_marker",
    "find_openclaw_official_provider_in_text",
    "match_openclaw_builtin_model_provider",
]
