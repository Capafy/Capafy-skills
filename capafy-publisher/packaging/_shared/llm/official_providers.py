from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from packaging._shared.common.constants import (
    ANTHROPIC_OFFICIAL_URL,
    GOOGLE_OFFICIAL_URL,
    OPENAI_OFFICIAL_URL_V1,
)
from packaging._shared.llm.api_formats import (
    PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES,
    PLATFORM_API_FORMAT_GOOGLE_GENERATIVE_AI,
    PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
    PLATFORM_API_FORMAT_OPENAI_RESPONSES,
)


@dataclass(frozen=True)
class OfficialProviderSpec:
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


ALL_OFFICIAL_PROVIDER_SPECS = (
    OfficialProviderSpec(
        family="openai",
        service="OpenAI",
        provider_name="publisher_openai_official",
        api=PLATFORM_API_FORMAT_OPENAI_RESPONSES,
        base_url=OPENAI_OFFICIAL_URL_V1,
        markers=("openai", "chatgpt", "codex"),
        model_prefixes=("openai/",),
        live_single_env="OPENCLAW_LIVE_OPENAI_KEY",
        list_env_names=("OPENAI_API_KEYS",),
        primary_env_names=("OPENAI_API_KEY",),
        env_prefixes=("OPENAI_API_KEY_",),
    ),
    OfficialProviderSpec(
        family="anthropic",
        service="Anthropic",
        provider_name="publisher_anthropic_official",
        api=PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES,
        base_url=ANTHROPIC_OFFICIAL_URL,
        markers=("anthropic", "claude"),
        model_prefixes=("anthropic/", "claude/"),
        live_single_env="OPENCLAW_LIVE_ANTHROPIC_KEY",
        list_env_names=("OPENCLAW_LIVE_ANTHROPIC_KEYS", "ANTHROPIC_API_KEYS"),
        primary_env_names=("ANTHROPIC_API_KEY",),
        env_prefixes=("ANTHROPIC_API_KEY_",),
    ),
    OfficialProviderSpec(
        family="google",
        service="Google",
        provider_name="publisher_google_official",
        api=PLATFORM_API_FORMAT_GOOGLE_GENERATIVE_AI,
        base_url=GOOGLE_OFFICIAL_URL,
        markers=("gemini", "google"),
        model_prefixes=("google/",),
        live_single_env="OPENCLAW_LIVE_GEMINI_KEY",
        list_env_names=("GEMINI_API_KEYS",),
        primary_env_names=("GEMINI_API_KEY",),
        env_prefixes=("GEMINI_API_KEY_",),
        fallback_env_names=("GOOGLE_API_KEY",),
    ),
    OfficialProviderSpec(
        family="nous",
        service="Nous Portal",
        provider_name="publisher_nous_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://inference-api.nousresearch.com/v1",
        markers=("nous", "nous-portal"),
        model_prefixes=("nous/",),
        primary_env_names=("NOUS_API_KEY",),
    ),
    OfficialProviderSpec(
        family="deepseek",
        service="DeepSeek",
        provider_name="publisher_deepseek_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://api.deepseek.com/v1",
        markers=("deepseek",),
        model_prefixes=("deepseek/",),
        primary_env_names=("DEEPSEEK_API_KEY",),
    ),
    OfficialProviderSpec(
        family="xai",
        service="xAI",
        provider_name="publisher_xai_official",
        api=PLATFORM_API_FORMAT_OPENAI_RESPONSES,
        base_url="https://api.x.ai/v1",
        markers=("xai", "x.ai", "grok", "supergrok"),
        model_prefixes=("xai/", "x-ai/"),
        primary_env_names=("XAI_API_KEY",),
    ),
    OfficialProviderSpec(
        family="zai",
        service="Z.AI",
        provider_name="publisher_zai_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://api.z.ai/api/paas/v4",
        markers=("zai", "z.ai", "zhipu", "glm"),
        model_prefixes=("zai/", "glm/"),
        primary_env_names=("ZAI_API_KEY", "ZHIPUAI_API_KEY"),
    ),
    OfficialProviderSpec(
        family="moonshot",
        service="Moonshot",
        provider_name="publisher_moonshot_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://api.moonshot.cn/v1",
        markers=("moonshot", "kimi", "kimi-coding"),
        model_prefixes=("moonshot/", "kimi/"),
        primary_env_names=("MOONSHOT_API_KEY", "KIMI_API_KEY"),
    ),
    OfficialProviderSpec(
        family="minimax",
        service="MiniMax",
        provider_name="publisher_minimax_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://api.minimax.chat/v1",
        markers=("minimax",),
        model_prefixes=("minimax/",),
        primary_env_names=("MINIMAX_API_KEY",),
    ),
    OfficialProviderSpec(
        family="openrouter",
        service="OpenRouter",
        provider_name="publisher_openrouter_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://openrouter.ai/api/v1",
        markers=("openrouter",),
        model_prefixes=("openrouter/",),
        primary_env_names=("OPENROUTER_API_KEY",),
    ),
)

ALL_OFFICIAL_PROVIDER_SPECS_BY_NAME = {
    spec.provider_name: spec
    for spec in ALL_OFFICIAL_PROVIDER_SPECS
}
ALL_OFFICIAL_PROVIDER_SPECS_BY_FAMILY = {
    spec.family: spec
    for spec in ALL_OFFICIAL_PROVIDER_SPECS
}


def match_official_builtin_model_provider(
    model_ref: str,
    *,
    specs: tuple[OfficialProviderSpec, ...] = ALL_OFFICIAL_PROVIDER_SPECS,
) -> Optional[tuple[OfficialProviderSpec, str]]:
    normalized = str(model_ref or "").strip()
    lowered = normalized.lower()
    for spec in specs:
        for prefix in spec.model_prefixes:
            if lowered.startswith(prefix):
                return spec, normalized[len(prefix):]
    if "/" not in normalized:
        for spec in specs:
            if spec.family == "anthropic" and lowered.startswith("claude-"):
                return spec, normalized
    return None


def find_official_provider_by_marker(
    value: str,
    *,
    specs: tuple[OfficialProviderSpec, ...] = ALL_OFFICIAL_PROVIDER_SPECS,
    match_provider_identity: bool = True,
) -> Optional[OfficialProviderSpec]:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    for spec in specs:
        if match_provider_identity:
            if spec.provider_name.lower() == normalized:
                return spec
            if spec.family == normalized:
                return spec
        if any(marker == normalized for marker in spec.markers):
            return spec
    return None


def find_official_provider_in_text(
    value: str,
    *,
    specs: tuple[OfficialProviderSpec, ...] = ALL_OFFICIAL_PROVIDER_SPECS,
    match_provider_identity: bool = True,
) -> Optional[OfficialProviderSpec]:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    for spec in specs:
        if match_provider_identity and spec.provider_name.lower() in normalized:
            return spec
        if any(marker in normalized for marker in spec.markers):
            return spec
    return None


def find_official_provider_by_base_url(value: str) -> Optional[OfficialProviderSpec]:
    normalized = str(value or "").strip().rstrip("/")
    if not normalized:
        return None
    for spec in ALL_OFFICIAL_PROVIDER_SPECS:
        if normalized == spec.base_url.rstrip("/"):
            return spec
    return None


__all__ = [
    "ALL_OFFICIAL_PROVIDER_SPECS",
    "ALL_OFFICIAL_PROVIDER_SPECS_BY_FAMILY",
    "ALL_OFFICIAL_PROVIDER_SPECS_BY_NAME",
    "OfficialProviderSpec",
    "find_official_provider_by_base_url",
    "find_official_provider_by_marker",
    "find_official_provider_in_text",
    "match_official_builtin_model_provider",
]
