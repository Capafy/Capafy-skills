from __future__ import annotations

from dataclasses import dataclass

from packaging._shared.common.constants import (
    ANTHROPIC_OFFICIAL_URL,
    GOOGLE_OFFICIAL_URL,
    OPENAI_OFFICIAL_URL_V1,
)


@dataclass(frozen=True)
class OpenClawOfficialProviderSpec:
    family: str
    service: str
    provider_name: str
    api: str
    base_url: str
    markers: tuple[str, ...]
    model_prefixes: tuple[str, ...]
    live_single_env: str = ""
    list_env_names: tuple[str, ...] = ()
    primary_env_names: tuple[str, ...] = ()
    env_prefixes: tuple[str, ...] = ()
    fallback_env_names: tuple[str, ...] = ()

    @property
    def default_env_key(self) -> str:
        return self.primary_env_names[0] if self.primary_env_names else ""

    @property
    def exact_env_keys(self) -> tuple[str, ...]:
        ordered = [
            self.live_single_env,
            *self.list_env_names,
            *self.primary_env_names,
            *self.fallback_env_names,
        ]
        seen: set[str] = set()
        result: list[str] = []
        for item in ordered:
            normalized = str(item or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return tuple(result)

    @property
    def wildcard_env_prefixes(self) -> tuple[str, ...]:
        return self.env_prefixes


OPENCLAW_OFFICIAL_PROVIDER_SPECS = (
    OpenClawOfficialProviderSpec(
        family="openai",
        service="OpenAI",
        provider_name="publisher_openai_official",
        api="openai-responses",
        base_url=OPENAI_OFFICIAL_URL_V1,
        markers=("openai",),
        model_prefixes=("openai/",),
        live_single_env="OPENCLAW_LIVE_OPENAI_KEY",
        list_env_names=("OPENAI_API_KEYS",),
        primary_env_names=("OPENAI_API_KEY",),
        env_prefixes=("OPENAI_API_KEY_",),
    ),
    OpenClawOfficialProviderSpec(
        family="anthropic",
        service="Anthropic",
        provider_name="publisher_anthropic_official",
        api="anthropic-messages",
        base_url=ANTHROPIC_OFFICIAL_URL,
        markers=("anthropic", "claude"),
        model_prefixes=("anthropic/", "claude/"),
        live_single_env="OPENCLAW_LIVE_ANTHROPIC_KEY",
        list_env_names=("OPENCLAW_LIVE_ANTHROPIC_KEYS", "ANTHROPIC_API_KEYS"),
        primary_env_names=("ANTHROPIC_API_KEY",),
        env_prefixes=("ANTHROPIC_API_KEY_",),
    ),
    OpenClawOfficialProviderSpec(
        family="google",
        service="Google",
        provider_name="publisher_google_official",
        api="google-generative-ai",
        base_url=GOOGLE_OFFICIAL_URL,
        markers=("gemini", "google"),
        model_prefixes=("google/",),
        live_single_env="OPENCLAW_LIVE_GEMINI_KEY",
        list_env_names=("GEMINI_API_KEYS",),
        primary_env_names=("GEMINI_API_KEY",),
        env_prefixes=("GEMINI_API_KEY_",),
        fallback_env_names=("GOOGLE_API_KEY",),
    ),
)

OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME = {
    spec.provider_name: spec
    for spec in OPENCLAW_OFFICIAL_PROVIDER_SPECS
}


def match_openclaw_builtin_model_provider(
    model_ref: str,
) -> tuple[OpenClawOfficialProviderSpec, str] | None:
    normalized = str(model_ref or "").strip()
    lowered = normalized.lower()
    for spec in OPENCLAW_OFFICIAL_PROVIDER_SPECS:
        for prefix in spec.model_prefixes:
            if lowered.startswith(prefix):
                return spec, normalized[len(prefix):]
    return None


def find_openclaw_official_provider_by_marker(
    value: str,
) -> OpenClawOfficialProviderSpec | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    for spec in OPENCLAW_OFFICIAL_PROVIDER_SPECS:
        if any(marker == normalized for marker in spec.markers):
            return spec
    return None


def find_openclaw_official_provider_in_text(
    value: str,
) -> OpenClawOfficialProviderSpec | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    for spec in OPENCLAW_OFFICIAL_PROVIDER_SPECS:
        if any(marker in normalized for marker in spec.markers):
            return spec
    return None


__all__ = [
    "OPENCLAW_OFFICIAL_PROVIDER_SPECS",
    "OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME",
    "OpenClawOfficialProviderSpec",
    "find_openclaw_official_provider_by_marker",
    "find_openclaw_official_provider_in_text",
    "match_openclaw_builtin_model_provider",
]
