from __future__ import annotations
from typing import Optional

from packaging._shared.llm.api_formats import PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES
from packaging._shared.llm.official_providers import (
    OfficialProviderSpec,
    OfficialProviderSpecOverride,
    build_official_provider_specs,
    find_official_provider_by_marker,
    match_official_builtin_model_provider,
)


OpenClawOfficialProviderSpec = OfficialProviderSpec


_OPENCLAW_OFFICIAL_PROVIDER_FAMILIES = {
    "openai",
    "anthropic",
    "google",
    "zai",
    "moonshot",
    "deepseek",
    "xai",
    "openrouter",
    "arcee",
    "gmi",
    "kilocode",
    "minimax",
    "novita",
    "nvidia",
    "qwen",
    "stepfun-plan",
    "tencent-tokenhub",
    "xiaomi",
    "byteplus-plan",
    "byteplus",
    "cerebras",
    "chutes",
    "cohere",
    "deepinfra",
    "fireworks",
    "groq",
    "mistral",
    "qianfan",
    "qwen-oauth",
    "stepfun",
    "together",
    "venice",
    "volcengine-plan",
    "volcengine",
    "xiaomi-token-plan",
}


OPENCLAW_OFFICIAL_PROVIDER_OVERRIDES = {
    "openai": OfficialProviderSpecOverride(
        fallback_env_names=("CODEX_API_KEY",),
    ),
    "zai": OfficialProviderSpecOverride(
        markers=("zai", "z.ai", "z-ai", "zhipu", "glm"),
        primary_env_names=("ZAI_API_KEY",),
        fallback_env_names=("Z_AI_API_KEY",),
    ),
    "moonshot": OfficialProviderSpecOverride(
        base_url="https://api.moonshot.ai/v1",
        markers=("moonshot", "moonshot-ai", "moonshotai"),
        model_prefixes=("moonshot/",),
        primary_env_names=("MOONSHOT_API_KEY",),
        fallback_env_names=("KIMI_API_KEY",),
    ),
    "deepseek": OfficialProviderSpecOverride(
        base_url="https://api.deepseek.com",
    ),
    "kilocode": OfficialProviderSpecOverride(
        base_url="https://api.kilo.ai/api/gateway/",
    ),
    "minimax": OfficialProviderSpecOverride(
        api=PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES,
        base_url="https://api.minimax.io/anthropic",
        markers=("minimax", "minimax-api", "minimax-cn", "minimax-api-key-cn", "minimax-cloud"),
        model_prefixes=("minimax/", "minimax-cn/"),
        primary_env_names=("MINIMAX_CODE_PLAN_KEY", "MINIMAX_CODING_API_KEY", "MINIMAX_API_KEY"),
    ),
    "novita": OfficialProviderSpecOverride(
        service="Novita",
    ),
    "nvidia": OfficialProviderSpecOverride(
        service="NVIDIA",
    ),
}


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


OPENCLAW_OFFICIAL_PROVIDER_SPECS = build_official_provider_specs(
    _OPENCLAW_OFFICIAL_PROVIDER_FAMILIES,
    overrides=OPENCLAW_OFFICIAL_PROVIDER_OVERRIDES,
) + (
    OfficialProviderSpec(
        family="kimi",
        service="Kimi Coding",
        provider_name="publisher_kimi_official",
        api=PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES,
        base_url="https://api.kimi.com/coding/",
        markers=("kimi", "kimi-coding", "kimi-code", "kimicode"),
        model_prefixes=("kimi/",),
        primary_env_names=("KIMI_API_KEY",),
        fallback_env_names=("KIMICODE_API_KEY",),
    ),
)
OPENCLAW_OFFICIAL_PROVIDER_SPECS = _sort_openclaw_official_specs(
    OPENCLAW_OFFICIAL_PROVIDER_SPECS
)

OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME = {
    spec.provider_name: spec
    for spec in OPENCLAW_OFFICIAL_PROVIDER_SPECS
}
OPENCLAW_OFFICIAL_PROVIDER_NAMES_BY_MARKER = {
    marker: spec.provider_name
    for spec in OPENCLAW_OFFICIAL_PROVIDER_SPECS
    for marker in spec.markers
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
    normalized = str(value or "").strip().lower()
    if not normalized:
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
    "OPENCLAW_OFFICIAL_PROVIDER_NAMES_BY_MARKER",
    "OPENCLAW_OFFICIAL_PROVIDER_SPECS",
    "OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME",
    "OpenClawOfficialProviderSpec",
    "find_openclaw_official_provider_by_marker",
    "find_openclaw_official_provider_in_text",
    "match_openclaw_builtin_model_provider",
]
