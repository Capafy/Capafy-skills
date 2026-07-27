from __future__ import annotations

from typing import Optional

from packaging._shared.llm.api_formats import (
    PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES,
    PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
)
from packaging._shared.llm.official_providers import (
    OfficialProviderSpecOverride,
    OfficialProviderSpec as HermesOfficialProviderSpec,
    build_official_provider_specs,
    find_official_provider_by_base_url,
    find_official_provider_by_marker,
)


_HERMES_OFFICIAL_PROVIDER_FAMILIES = {
    "openai",
    "anthropic",
    "google",
    "nous",
    "deepseek",
    "xai",
    "zai",
    "moonshot",
    "minimax",
    "openrouter",
    "alibaba",
    "alibaba-coding-plan",
    "arcee",
    "gmi",
    "huggingface",
    "kilocode",
    "kimi-coding-cn",
    "minimax-cn",
    "novita",
    "nvidia",
    "ollama-cloud",
    "opencode-go",
    "opencode-zen",
    "stepfun",
    "tencent-tokenhub",
    "xiaomi",
}


_HERMES_OFFICIAL_PROVIDER_OVERRIDES = {
    "openai": OfficialProviderSpecOverride(
        markers=("openai", "openai-api"),
    ),
    "anthropic": OfficialProviderSpecOverride(
        markers=("anthropic", "claude", "claude-oauth", "claude-code"),
        primary_env_names=("ANTHROPIC_API_KEY", "ANTHROPIC_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"),
    ),
    "google": OfficialProviderSpecOverride(
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://generativelanguage.googleapis.com/v1beta",
        markers=("gemini", "google", "google-gemini", "google-ai-studio"),
        primary_env_names=("GOOGLE_API_KEY", "GEMINI_API_KEY"),
        fallback_env_names=(),
    ),
    "xai": OfficialProviderSpecOverride(
        markers=("xai", "grok", "x-ai", "x.ai"),
    ),
    "zai": OfficialProviderSpecOverride(
        markers=("zai", "glm", "z-ai", "z.ai", "zhipu"),
        primary_env_names=("GLM_API_KEY", "ZAI_API_KEY", "Z_AI_API_KEY"),
        fallback_env_names=(),
    ),
    "moonshot": OfficialProviderSpecOverride(
        service="Kimi / Moonshot",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://api.moonshot.ai/v1",
        markers=("kimi-coding", "kimi", "moonshot", "kimi-for-coding"),
        model_prefixes=("kimi/", "moonshot/"),
        primary_env_names=("KIMI_API_KEY", "KIMI_CODING_API_KEY"),
        fallback_env_names=(),
    ),
    "minimax": OfficialProviderSpecOverride(
        api=PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES,
        base_url="https://api.minimax.io/anthropic",
        markers=("minimax", "mini-max"),
        model_prefixes=("minimax/",),
        primary_env_names=("MINIMAX_API_KEY",),
    ),
    "openrouter": OfficialProviderSpecOverride(
        markers=("openrouter", "or"),
    ),
    "stepfun": OfficialProviderSpecOverride(
        service="StepFun Step Plan",
        base_url="https://api.stepfun.ai/step_plan/v1",
        markers=("stepfun", "step", "stepfun-coding-plan"),
    ),
}


HERMES_OFFICIAL_PROVIDER_SPECS = build_official_provider_specs(
    _HERMES_OFFICIAL_PROVIDER_FAMILIES,
    overrides=_HERMES_OFFICIAL_PROVIDER_OVERRIDES,
)

HERMES_OFFICIAL_PROVIDER_SPECS_BY_NAME = {
    spec.provider_name: spec
    for spec in HERMES_OFFICIAL_PROVIDER_SPECS
}
HERMES_OFFICIAL_PROVIDER_SPECS_BY_FAMILY = {
    spec.family: spec
    for spec in HERMES_OFFICIAL_PROVIDER_SPECS
}


def find_hermes_official_provider_by_marker(
    value: str,
) -> Optional[HermesOfficialProviderSpec]:
    return find_official_provider_by_marker(
        value,
        specs=HERMES_OFFICIAL_PROVIDER_SPECS,
    )


def find_hermes_official_provider_by_base_url(
    value: str,
) -> Optional[HermesOfficialProviderSpec]:
    return find_official_provider_by_base_url(
        value,
        specs=HERMES_OFFICIAL_PROVIDER_SPECS,
    )


__all__ = [
    "HERMES_OFFICIAL_PROVIDER_SPECS",
    "HERMES_OFFICIAL_PROVIDER_SPECS_BY_FAMILY",
    "HERMES_OFFICIAL_PROVIDER_SPECS_BY_NAME",
    "HermesOfficialProviderSpec",
    "find_hermes_official_provider_by_base_url",
    "find_hermes_official_provider_by_marker",
]
