from __future__ import annotations

from dataclasses import dataclass
from typing import Collection, Mapping, Optional, Union

from packaging.common.constants import (
    ANTHROPIC_OFFICIAL_URL,
    GOOGLE_OFFICIAL_URL,
    OPENAI_OFFICIAL_URL_V1,
)
from packaging.runtime.llm.api_formats import (
    PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES,
    PLATFORM_API_FORMAT_GOOGLE_GENERATIVE_AI,
    PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
    PLATFORM_API_FORMAT_OPENAI_RESPONSES,
    SUPPORTED_PLATFORM_API_FORMATS,
    is_supported_platform_api_format,
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


@dataclass(frozen=True)
class ProviderEnvMetadata:
    """Provider auth variable metadata; values are never resolved here."""

    key_env_names: tuple[str, ...] = ()
    route_hint_env_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProviderPlatformConfig:
    service: Optional[str] = None
    provider_name: Optional[str] = None
    api: Optional[str] = None
    base_url: Optional[str] = None
    markers: Optional[tuple[str, ...]] = None
    model_prefixes: Optional[tuple[str, ...]] = None
    key_env_names: Optional[tuple[str, ...]] = None
    route_hint_env_names: Optional[tuple[str, ...]] = None


@dataclass(frozen=True)
class ProviderDefinition:
    family: str
    service: str
    provider_name: str
    api: str
    base_url: str
    markers: tuple[str, ...]
    model_prefixes: tuple[str, ...]
    platforms: Mapping[str, ProviderPlatformConfig]
    key_env_names: tuple[str, ...] = ()
    route_hint_env_names: tuple[str, ...] = ()
    base_url_aliases: tuple[str, ...] = ()
    generic: Optional[ProviderPlatformConfig] = None
    include_in_all: bool = True

    def official_spec(self, platform: Optional[str] = None) -> Optional[OfficialProviderSpec]:
        config = self.generic
        if platform is not None:
            config = self.platforms.get(str(platform or "").strip().lower())
            if config is None:
                return None
        return OfficialProviderSpec(
            family=self.family,
            service=config.service if config and config.service is not None else self.service,
            provider_name=config.provider_name if config and config.provider_name is not None else self.provider_name,
            api=config.api if config and config.api is not None else self.api,
            base_url=config.base_url if config and config.base_url is not None else self.base_url,
            markers=config.markers if config and config.markers is not None else self.markers,
            model_prefixes=(
                config.model_prefixes
                if config and config.model_prefixes is not None
                else self.model_prefixes
            ),
        )


def _name_tuple(value: Union[str, tuple[str, ...]]) -> tuple[str, ...]:
    return (value,) if isinstance(value, str) else value


def _platform(
    *,
    service: Optional[str] = None,
    provider_name: Optional[str] = None,
    api: Optional[str] = None,
    base_url: Optional[str] = None,
    markers: Optional[tuple[str, ...]] = None,
    model_prefixes: Optional[tuple[str, ...]] = None,
    keys: Optional[Union[str, tuple[str, ...]]] = None,
    route_hints: Optional[Union[str, tuple[str, ...]]] = None,
) -> ProviderPlatformConfig:
    key_env_names = None if keys is None else _name_tuple(keys)
    return ProviderPlatformConfig(
        service=service,
        provider_name=provider_name,
        api=api,
        base_url=base_url,
        markers=markers,
        model_prefixes=model_prefixes,
        key_env_names=key_env_names,
        route_hint_env_names=(
            key_env_names if route_hints is None else _name_tuple(route_hints)
        ),
    )


def _provider(
    family: str,
    service: str,
    base_url: str,
    *,
    api: str = PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
    provider_name: str = "",
    markers: Optional[tuple[str, ...]] = None,
    model_prefixes: Optional[tuple[str, ...]] = None,
    on: tuple[str, ...] = (),
    keys: Optional[Union[str, tuple[str, ...]]] = None,
    route_hints: Optional[Union[str, tuple[str, ...]]] = None,
    base_url_aliases: tuple[str, ...] = (),
    generic: Optional[ProviderPlatformConfig] = None,
    hermes: Optional[ProviderPlatformConfig] = None,
    openclaw: Optional[ProviderPlatformConfig] = None,
    include_in_all: bool = True,
) -> ProviderDefinition:
    overrides = {"hermes": hermes, "openclaw": openclaw}
    platforms = {platform: overrides.get(platform) or _platform() for platform in on}
    key_env_names = () if keys is None else _name_tuple(keys)
    route_hint_env_names = key_env_names if route_hints is None else _name_tuple(route_hints)
    return ProviderDefinition(
        family=family,
        service=service,
        provider_name=provider_name or f"publisher_{family.replace('-', '_')}_official",
        api=api,
        base_url=base_url,
        markers=markers if markers is not None else (family,),
        model_prefixes=model_prefixes if model_prefixes is not None else (f"{family}/",),
        platforms=platforms,
        key_env_names=key_env_names,
        route_hint_env_names=route_hint_env_names,
        base_url_aliases=base_url_aliases,
        generic=generic,
        include_in_all=include_in_all,
    )


_HERMES = ("hermes",)
_OPENCLAW = ("openclaw",)
_BOTH = (*_HERMES, *_OPENCLAW)


PROVIDER_CATALOG = (
    _provider(
        "openai", "OpenAI", OPENAI_OFFICIAL_URL_V1,
        api=PLATFORM_API_FORMAT_OPENAI_RESPONSES,
        markers=("openai", "chatgpt", "codex"),
        on=_OPENCLAW,
        keys=("OPENAI_API_KEY", "CODEX_API_KEY"),
    ),
    _provider(
        "anthropic", "Anthropic", ANTHROPIC_OFFICIAL_URL,
        api=PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES,
        markers=("anthropic", "claude"),
        model_prefixes=("anthropic/", "claude/"),
        on=_BOTH,
        hermes=_platform(
            markers=("anthropic", "claude", "claude-code"),
            keys=("ANTHROPIC_API_KEY", "ANTHROPIC_TOKEN"),
        ),
        openclaw=_platform(keys="ANTHROPIC_API_KEY"),
    ),
    _provider(
        "google", "Google", GOOGLE_OFFICIAL_URL,
        api=PLATFORM_API_FORMAT_GOOGLE_GENERATIVE_AI,
        markers=("gemini", "google"),
        on=_BOTH,
        hermes=_platform(
            base_url="https://generativelanguage.googleapis.com/v1beta",
            markers=("gemini", "google", "google-gemini", "google-ai-studio"),
            keys=("GOOGLE_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY", "GEMINI_API_KEY"),
        ),
        openclaw=_platform(keys=("GOOGLE_API_KEY", "GEMINI_API_KEY")),
    ),
    _provider(
        "nous", "Nous Portal", "https://inference-api.nousresearch.com/v1",
        markers=("nous", "nous-portal"), on=_HERMES,
    ),
    _provider(
        "deepseek", "DeepSeek", "https://api.deepseek.com",
        on=_BOTH, keys="DEEPSEEK_API_KEY",
        base_url_aliases=("https://api.deepseek.com/v1",),
    ),
    _provider(
        "xai", "xAI", "https://api.x.ai/v1",
        api=PLATFORM_API_FORMAT_OPENAI_RESPONSES,
        markers=("xai", "x.ai", "grok", "supergrok"),
        model_prefixes=("xai/", "x-ai/"),
        on=_BOTH,
        keys="XAI_API_KEY",
        hermes=_platform(markers=("xai", "grok", "x-ai", "x.ai")),
    ),
    _provider(
        "zai", "Z.AI", "https://api.z.ai/api/paas/v4",
        markers=("zai", "z.ai", "zhipu", "glm"),
        model_prefixes=("zai/", "glm/"),
        on=_BOTH,
        hermes=_platform(
            markers=("zai", "glm", "z-ai", "z.ai", "zhipu"),
            keys=("GLM_API_KEY", "ZAI_API_KEY", "Z_AI_API_KEY", "ZHIPU_API_KEY", "ZHIPUAI_API_KEY"),
        ),
        openclaw=_platform(
            markers=("zai", "z.ai", "z-ai", "zhipu", "glm"),
            keys=("ZAI_API_KEY", "Z_AI_API_KEY"),
            route_hints=(),
        ),
    ),
    _provider(
        "moonshot", "Moonshot", "https://api.moonshot.ai/v1",
        markers=("moonshot", "moonshot-ai", "moonshotai"),
        model_prefixes=("moonshot/",),
        on=_OPENCLAW,
        keys=("MOONSHOT_API_KEY", "KIMI_API_KEY"),
        route_hints=(),
        base_url_aliases=("https://api.moonshot.cn/v1",),
    ),
    _provider(
        "kimi", "Kimi Coding", "https://api.kimi.com/coding",
        api=PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES,
        markers=("kimi", "kimi-coding"),
        on=_BOTH,
        hermes=_platform(
            markers=("kimi-for-coding", "kimi-coding", "kimi", "moonshot"),
            model_prefixes=("kimi/", "moonshot/"),
            keys=("KIMI_API_KEY", "KIMI_CODING_API_KEY"),
            route_hints="KIMI_CODING_API_KEY",
        ),
        openclaw=_platform(
            markers=("kimi", "kimi-coding", "kimi-code", "kimicode"),
            keys=("KIMI_API_KEY", "KIMICODE_API_KEY"),
            route_hints=(),
        ),
    ),
    _provider(
        "kimi-coding-cn", "Kimi / Moonshot (China)", "https://api.moonshot.cn/v1",
        provider_name="publisher_kimi_cn_official",
        markers=("kimi-coding-cn", "kimi-cn", "moonshot-cn"),
        model_prefixes=("kimi-cn/", "moonshot-cn/"),
        on=_HERMES,
        keys="KIMI_CN_API_KEY",
    ),
    _provider(
        "minimax", "MiniMax", "https://api.minimax.io/anthropic",
        api=PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES,
        on=_BOTH,
        generic=_platform(
            api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
            base_url="https://api.minimax.io/v1",
        ),
        hermes=_platform(
            markers=("minimax", "mini-max"),
            keys="MINIMAX_API_KEY",
        ),
        openclaw=_platform(
            markers=("minimax", "minimax-api", "minimax-cloud"),
            model_prefixes=("minimax/",),
            keys=("MINIMAX_CODE_PLAN_KEY", "MINIMAX_CODING_API_KEY", "MINIMAX_API_KEY"),
            route_hints=(),
        ),
    ),
    _provider(
        "openrouter", "OpenRouter", "https://openrouter.ai/api/v1",
        on=_BOTH,
        keys="OPENROUTER_API_KEY",
        hermes=_platform(markers=("openrouter", "openai", "or")),
    ),
    _provider(
        "arcee", "Arcee AI", "https://api.arcee.ai/api/v1",
        markers=("arcee", "arceeai", "arcee-ai"), on=_BOTH, keys="ARCEEAI_API_KEY",
    ),
    _provider(
        "alibaba-coding-plan", "Alibaba Cloud (Coding Plan)", "https://coding-intl.dashscope.aliyuncs.com/v1",
        markers=("alibaba-coding-plan", "alibaba_coding", "alibaba-coding", "dashscope-coding"),
        model_prefixes=("alibaba-coding-plan/", "dashscope-coding/"),
        on=_BOTH,
        keys="ALIBABA_CODING_PLAN_API_KEY",
        openclaw=_platform(
            service="Qwen Coding",
            provider_name="publisher_qwen_official",
            markers=(
                "qwen", "qwencloud", "alibaba-coding", "alibaba-coding-plan",
                "dashscope-coding", "modelstudio-api-key", "qwen-api-key",
            ),
            model_prefixes=("qwen/", "qwencloud/"),
            keys=("QWEN_API_KEY", "MODELSTUDIO_API_KEY", "DASHSCOPE_API_KEY", "ALIBABA_CODING_PLAN_API_KEY"),
            route_hints=(),
        ),
    ),
    _provider(
        "gmi", "GMI Cloud", "https://api.gmi-serving.com/v1",
        markers=("gmi", "gmi-cloud", "gmicloud"), on=_BOTH, keys="GMI_API_KEY",
    ),
    _provider(
        "huggingface", "Hugging Face", "https://router.huggingface.co/v1",
        markers=("huggingface", "hf", "hugging-face", "huggingface-hub"),
        model_prefixes=("huggingface/", "hf/"),
        on=_HERMES,
        keys="HF_TOKEN",
    ),
    _provider(
        "kilocode", "Kilo Code", "https://api.kilo.ai/api/gateway",
        markers=("kilocode", "kilo-code", "kilo", "kilo-gateway"),
        on=_BOTH,
        keys="KILOCODE_API_KEY",
        hermes=_platform(markers=("kilo", "kilocode", "kilo-code", "kilo-gateway")),
        openclaw=_platform(base_url="https://api.kilo.ai/api/gateway/"),
    ),
    _provider(
        "minimax-cn", "MiniMax (China)", "https://api.minimaxi.com/anthropic",
        api=PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES,
        markers=("minimax-cn", "minimax-china", "minimax_cn"),
        on=_HERMES,
        keys="MINIMAX_CN_API_KEY",
        base_url_aliases=("https://api.minimaxi.com/anthropic/v1",),
    ),
    _provider(
        "novita", "NovitaAI", "https://api.novita.ai/openai/v1",
        markers=("novita", "novita-ai", "novitaai"),
        on=_BOTH,
        keys="NOVITA_API_KEY",
        openclaw=_platform(service="Novita"),
    ),
    _provider(
        "nvidia", "NVIDIA NIM", "https://integrate.api.nvidia.com/v1",
        markers=("nvidia", "nvidia-nim"),
        on=_BOTH,
        keys="NVIDIA_API_KEY",
        openclaw=_platform(service="NVIDIA"),
    ),
    _provider(
        "ollama-cloud", "Ollama Cloud", "https://ollama.com/v1",
        markers=("ollama-cloud", "ollama_cloud"), on=_HERMES, keys="OLLAMA_API_KEY",
    ),
    _provider(
        "opencode-zen", "OpenCode Zen", "https://opencode.ai/zen/v1",
        markers=("opencode", "opencode-zen", "zen"),
        model_prefixes=("opencode-zen/", "opencode/"),
        on=_BOTH,
        generic=_platform(markers=("opencode-zen", "opencode", "opencode_zen", "zen")),
        hermes=_platform(keys="OPENCODE_ZEN_API_KEY"),
        openclaw=_platform(
            keys=("OPENCODE_API_KEY", "OPENCODE_ZEN_API_KEY"),
            route_hints=(),
        ),
    ),
    _provider(
        "opencode-go", "OpenCode Go", "https://opencode.ai/zen/go/v1",
        markers=("opencode-go", "opencode_go", "go", "opencode-go-sub"),
        on=_BOTH,
        hermes=_platform(keys="OPENCODE_GO_API_KEY"),
        openclaw=_platform(
            keys=("OPENCODE_API_KEY", "OPENCODE_ZEN_API_KEY"),
            route_hints=(),
        ),
    ),
    _provider(
        "qwen-token-plan", "Qwen Token Plan", "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
        markers=("qwen-token-plan", "bailian-token-plan"),
        model_prefixes=("qwen-token-plan/",),
        on=_OPENCLAW,
        keys="QWEN_TOKEN_PLAN_API_KEY",
        route_hints=(),
    ),
    _provider(
        "alibaba", "Qwen Cloud", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        markers=("alibaba", "dashscope", "alibaba-cloud", "qwen-dashscope"),
        model_prefixes=("alibaba/", "dashscope/", "qwen/"),
        on=_HERMES,
        keys="DASHSCOPE_API_KEY",
    ),
    _provider(
        "stepfun-plan", "StepFun Plan", "https://api.stepfun.ai/step_plan/v1",
        markers=("stepfun-plan", "step-fun-plan", "stepfun-coding-plan"),
        model_prefixes=("stepfun-plan/",),
        on=_BOTH,
        keys="STEPFUN_API_KEY",
        route_hints=(),
        hermes=_platform(
            service="StepFun Step Plan",
            markers=("stepfun", "step", "stepfun-coding-plan"),
            model_prefixes=("stepfun/", "stepfun-plan/"),
            keys="STEPFUN_API_KEY",
            route_hints="STEPFUN_API_KEY",
        ),
    ),
    _provider(
        "stepfun", "StepFun", "https://api.stepfun.ai/v1",
        markers=("stepfun", "step-fun"),
        model_prefixes=("stepfun/",),
        on=_OPENCLAW,
        keys="STEPFUN_API_KEY",
        route_hints=(),
    ),
    _provider(
        "tencent-tokenhub", "Tencent TokenHub", "https://tokenhub.tencentmaas.com/v1",
        markers=("tencent-tokenhub", "tokenhub", "tencent", "tencent-cloud", "tencentmaas", "tencent-maas"),
        on=_BOTH,
        keys="TOKENHUB_API_KEY",
    ),
    _provider(
        "xiaomi", "Xiaomi MiMo", "https://api.xiaomimimo.com/v1",
        markers=("xiaomi", "mimo", "xiaomi-mimo"), on=_BOTH, keys="XIAOMI_API_KEY",
    ),
    _provider(
        "byteplus-plan", "BytePlus Coding Plan", "https://ark.ap-southeast.bytepluses.com/api/coding/v3",
        markers=("byteplus-plan", "byteplus-coding-plan"),
        on=_OPENCLAW,
        keys="BYTEPLUS_API_KEY",
        route_hints=(),
    ),
    _provider(
        "byteplus", "BytePlus", "https://ark.ap-southeast.bytepluses.com/api/v3",
        on=_OPENCLAW, keys="BYTEPLUS_API_KEY", route_hints=(),
    ),
    _provider("cerebras", "Cerebras", "https://api.cerebras.ai/v1", on=_OPENCLAW, keys="CEREBRAS_API_KEY"),
    _provider("chutes", "Chutes", "https://llm.chutes.ai/v1", on=_OPENCLAW, keys="CHUTES_API_KEY"),
    _provider("cohere", "Cohere", "https://api.cohere.ai/compatibility/v1", on=_OPENCLAW, keys="COHERE_API_KEY"),
    _provider(
        "deepinfra", "DeepInfra", "https://api.deepinfra.com/v1/openai",
        markers=("deepinfra", "deep-infra"), on=_OPENCLAW, keys="DEEPINFRA_API_KEY",
    ),
    _provider(
        "fireworks", "Fireworks", "https://api.fireworks.ai/inference/v1",
        markers=("fireworks", "fireworks-ai"), on=_OPENCLAW, keys="FIREWORKS_API_KEY",
    ),
    _provider("groq", "Groq", "https://api.groq.com/openai/v1", on=_OPENCLAW, keys="GROQ_API_KEY"),
    _provider("mistral", "Mistral", "https://api.mistral.ai/v1", on=_OPENCLAW, keys="MISTRAL_API_KEY"),
    _provider(
        "qianfan", "Baidu Qianfan", "https://qianfan.baidubce.com/v2",
        markers=("qianfan", "baidu-qianfan"), on=_OPENCLAW, keys="QIANFAN_API_KEY",
    ),
    _provider(
        "qwen-oauth", "Qwen Portal", "https://portal.qwen.ai/v1",
        markers=("qwen-oauth", "qwen-portal", "qwen-cli"),
        model_prefixes=("qwen-oauth/", "qwen-portal/", "qwen-cli/"),
    ),
    _provider(
        "together", "Together AI", "https://api.together.xyz/v1",
        markers=("together", "together-ai"), on=_OPENCLAW, keys="TOGETHER_API_KEY",
    ),
    _provider(
        "venice", "Venice", "https://api.venice.ai/api/v1",
        markers=("venice", "venice-ai"), on=_OPENCLAW, keys="VENICE_API_KEY",
    ),
    _provider(
        "volcengine-plan", "Volcano Engine Coding Plan", "https://ark.cn-beijing.volces.com/api/coding/v3",
        markers=("volcengine-plan", "volcano-engine-plan", "doubao-plan"),
        on=_OPENCLAW,
        keys="VOLCANO_ENGINE_API_KEY",
        route_hints=(),
    ),
    _provider(
        "volcengine", "Volcano Engine", "https://ark.cn-beijing.volces.com/api/v3",
        markers=("volcengine", "volcano-engine", "doubao"),
        on=_OPENCLAW,
        keys="VOLCANO_ENGINE_API_KEY",
        route_hints=(),
    ),
    _provider(
        "xiaomi-token-plan", "Xiaomi MiMo Token Plan", "https://token-plan-sgp.xiaomimimo.com/v1",
        markers=("xiaomi-token-plan", "mimo-token-plan"),
        on=_OPENCLAW,
        keys="XIAOMI_TOKEN_PLAN_API_KEY",
    ),
    _provider(
        "openai-api", "OpenAI", OPENAI_OFFICIAL_URL_V1,
        api=PLATFORM_API_FORMAT_OPENAI_RESPONSES,
        provider_name="publisher_openai_official",
        on=_HERMES,
        keys="OPENAI_API_KEY",
        include_in_all=False,
    ),
)


_PROVIDER_DEFINITIONS_BY_FAMILY = {definition.family: definition for definition in PROVIDER_CATALOG}
ALL_OFFICIAL_PROVIDER_SPECS = tuple(
    spec
    for definition in PROVIDER_CATALOG
    if definition.include_in_all
    if (spec := definition.official_spec()) is not None
)
ALL_OFFICIAL_PROVIDER_SPECS_BY_NAME = {spec.provider_name: spec for spec in ALL_OFFICIAL_PROVIDER_SPECS}
ALL_OFFICIAL_PROVIDER_SPECS_BY_FAMILY = {spec.family: spec for spec in ALL_OFFICIAL_PROVIDER_SPECS}


def build_platform_official_provider_specs(
    platform: str,
    families: Optional[Collection[str]] = None,
) -> tuple[OfficialProviderSpec, ...]:
    normalized_platform = str(platform or "").strip().lower()
    family_names = None if families is None else set(families)
    selected = tuple(
        spec
        for definition in PROVIDER_CATALOG
        if family_names is None or definition.family in family_names
        if (spec := definition.official_spec(normalized_platform)) is not None
    )
    _validate_official_provider_api_formats(selected)
    return selected


def provider_env_metadata(platform: str, family: str) -> ProviderEnvMetadata:
    normalized_platform = str(platform or "").strip().lower()
    normalized_family = str(family or "").strip().lower()
    definition = _PROVIDER_DEFINITIONS_BY_FAMILY.get(normalized_family)
    if definition is None:
        return ProviderEnvMetadata()
    config = definition.platforms.get(normalized_platform)
    if config is None:
        return ProviderEnvMetadata()
    return ProviderEnvMetadata(
        key_env_names=definition.key_env_names if config.key_env_names is None else config.key_env_names,
        route_hint_env_names=(
            definition.route_hint_env_names if config.route_hint_env_names is None else config.route_hint_env_names
        ),
    )


def find_official_provider_by_env_name(
    value: str,
    *,
    platform: str,
    specs: tuple[OfficialProviderSpec, ...],
) -> Optional[OfficialProviderSpec]:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    matches = [
        spec
        for spec in specs
        if normalized in provider_env_metadata(platform, spec.family).route_hint_env_names
    ]
    return matches[0] if len(matches) == 1 else None


def _validate_official_provider_api_formats(specs: tuple[OfficialProviderSpec, ...]) -> None:
    for spec in specs:
        if is_supported_platform_api_format(spec.api):
            continue
        supported = ", ".join(SUPPORTED_PLATFORM_API_FORMATS)
        raise ValueError(
            f"Unsupported official provider api_format for {spec.family}: {spec.api}. "
            f"Supported platform api_format values: {supported}"
        )


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


def find_official_provider_by_base_url(
    value: str,
    *,
    specs: tuple[OfficialProviderSpec, ...] = ALL_OFFICIAL_PROVIDER_SPECS,
) -> Optional[OfficialProviderSpec]:
    normalized = str(value or "").strip().rstrip("/")
    if not normalized:
        return None
    for spec in specs:
        definition = _PROVIDER_DEFINITIONS_BY_FAMILY.get(spec.family)
        aliases = definition.base_url_aliases if definition is not None else ()
        if normalized in {url.rstrip("/") for url in (spec.base_url, *aliases)}:
            return spec
    return None


__all__ = [
    "ALL_OFFICIAL_PROVIDER_SPECS",
    "ALL_OFFICIAL_PROVIDER_SPECS_BY_FAMILY",
    "ALL_OFFICIAL_PROVIDER_SPECS_BY_NAME",
    "OfficialProviderSpec",
    "PROVIDER_CATALOG",
    "ProviderDefinition",
    "ProviderEnvMetadata",
    "ProviderPlatformConfig",
    "build_platform_official_provider_specs",
    "find_official_provider_by_base_url",
    "find_official_provider_by_env_name",
    "find_official_provider_by_marker",
    "match_official_builtin_model_provider",
    "provider_env_metadata",
]
