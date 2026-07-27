from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Collection, Mapping, Optional

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


@dataclass(frozen=True)
class OfficialProviderSpecOverride:
    service: Optional[str] = None
    provider_name: Optional[str] = None
    api: Optional[str] = None
    base_url: Optional[str] = None
    markers: Optional[tuple[str, ...]] = None
    model_prefixes: Optional[tuple[str, ...]] = None
    live_single_env: Optional[str] = None
    list_env_names: Optional[tuple[str, ...]] = None
    primary_env_names: Optional[tuple[str, ...]] = None
    env_prefixes: Optional[tuple[str, ...]] = None
    fallback_env_names: Optional[tuple[str, ...]] = None

    def updates(self) -> dict[str, object]:
        return {
            field.name: value
            for field in fields(self)
            if (value := getattr(self, field.name)) is not None
        }


def _merge_official_provider_spec(
    spec: OfficialProviderSpec,
    override: OfficialProviderSpecOverride,
) -> OfficialProviderSpec:
    values = {
        field.name: getattr(spec, field.name)
        for field in fields(OfficialProviderSpec)
    }
    values.update(override.updates())
    return OfficialProviderSpec(**values)


def _apply_official_provider_overrides(
    specs: tuple[OfficialProviderSpec, ...],
    overrides: Mapping[str, OfficialProviderSpecOverride],
) -> tuple[OfficialProviderSpec, ...]:
    result: list[OfficialProviderSpec] = []
    for spec in specs:
        override = overrides.get(spec.family) or overrides.get(spec.provider_name)
        if override is None:
            result.append(spec)
            continue
        result.append(_merge_official_provider_spec(spec, override))
    return tuple(result)


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
    OfficialProviderSpec(
        family="arcee",
        service="Arcee AI",
        provider_name="publisher_arcee_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://api.arcee.ai/api/v1",
        markers=("arcee", "arceeai", "arcee-ai"),
        model_prefixes=("arcee/",),
        primary_env_names=("ARCEEAI_API_KEY",),
    ),
    OfficialProviderSpec(
        family="alibaba",
        service="Qwen Cloud",
        provider_name="publisher_alibaba_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        markers=("alibaba", "dashscope", "alibaba-cloud", "qwen-dashscope"),
        model_prefixes=("alibaba/", "dashscope/", "qwen/"),
        primary_env_names=("DASHSCOPE_API_KEY",),
    ),
    OfficialProviderSpec(
        family="alibaba-coding-plan",
        service="Alibaba Cloud (Coding Plan)",
        provider_name="publisher_alibaba_coding_plan_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://coding-intl.dashscope.aliyuncs.com/v1",
        markers=("alibaba-coding-plan", "alibaba_coding", "alibaba-coding", "dashscope-coding"),
        model_prefixes=("alibaba-coding-plan/", "dashscope-coding/"),
        primary_env_names=("ALIBABA_CODING_PLAN_API_KEY", "DASHSCOPE_API_KEY"),
    ),
    OfficialProviderSpec(
        family="gmi",
        service="GMI Cloud",
        provider_name="publisher_gmi_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://api.gmi-serving.com/v1",
        markers=("gmi", "gmi-cloud", "gmicloud"),
        model_prefixes=("gmi/",),
        primary_env_names=("GMI_API_KEY",),
    ),
    OfficialProviderSpec(
        family="huggingface",
        service="Hugging Face",
        provider_name="publisher_huggingface_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://router.huggingface.co/v1",
        markers=("huggingface", "hf", "hugging-face", "huggingface-hub"),
        model_prefixes=("huggingface/", "hf/"),
        primary_env_names=("HF_TOKEN",),
    ),
    OfficialProviderSpec(
        family="kilocode",
        service="Kilo Code",
        provider_name="publisher_kilocode_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://api.kilo.ai/api/gateway",
        markers=("kilocode", "kilo-code", "kilo", "kilo-gateway"),
        model_prefixes=("kilocode/",),
        primary_env_names=("KILOCODE_API_KEY",),
    ),
    OfficialProviderSpec(
        family="kimi-coding-cn",
        service="Kimi / Moonshot (China)",
        provider_name="publisher_kimi_cn_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://api.moonshot.cn/v1",
        markers=("kimi-coding-cn", "kimi-cn", "moonshot-cn"),
        model_prefixes=("kimi-cn/", "moonshot-cn/"),
        primary_env_names=("KIMI_CN_API_KEY",),
    ),
    OfficialProviderSpec(
        family="minimax-cn",
        service="MiniMax (China)",
        provider_name="publisher_minimax_cn_official",
        api=PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES,
        base_url="https://api.minimaxi.com/anthropic",
        markers=("minimax-cn", "minimax-china", "minimax_cn"),
        model_prefixes=("minimax-cn/",),
        primary_env_names=("MINIMAX_CN_API_KEY",),
    ),
    OfficialProviderSpec(
        family="novita",
        service="NovitaAI",
        provider_name="publisher_novita_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://api.novita.ai/openai/v1",
        markers=("novita", "novita-ai", "novitaai"),
        model_prefixes=("novita/",),
        primary_env_names=("NOVITA_API_KEY",),
    ),
    OfficialProviderSpec(
        family="nvidia",
        service="NVIDIA NIM",
        provider_name="publisher_nvidia_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://integrate.api.nvidia.com/v1",
        markers=("nvidia", "nvidia-nim"),
        model_prefixes=("nvidia/",),
        primary_env_names=("NVIDIA_API_KEY",),
    ),
    OfficialProviderSpec(
        family="ollama-cloud",
        service="Ollama Cloud",
        provider_name="publisher_ollama_cloud_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://ollama.com/v1",
        markers=("ollama-cloud", "ollama_cloud"),
        model_prefixes=("ollama-cloud/",),
        primary_env_names=("OLLAMA_API_KEY",),
    ),
    OfficialProviderSpec(
        family="opencode-zen",
        service="OpenCode Zen",
        provider_name="publisher_opencode_zen_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://opencode.ai/zen/v1",
        markers=("opencode-zen", "opencode", "opencode_zen", "zen"),
        model_prefixes=("opencode-zen/", "opencode/"),
        primary_env_names=("OPENCODE_ZEN_API_KEY",),
    ),
    OfficialProviderSpec(
        family="opencode-go",
        service="OpenCode Go",
        provider_name="publisher_opencode_go_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://opencode.ai/zen/go/v1",
        markers=("opencode-go", "opencode_go", "go", "opencode-go-sub"),
        model_prefixes=("opencode-go/",),
        primary_env_names=("OPENCODE_GO_API_KEY",),
    ),
    OfficialProviderSpec(
        family="qwen",
        service="Qwen Coding",
        provider_name="publisher_qwen_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://coding-intl.dashscope.aliyuncs.com/v1",
        markers=(
            "qwen",
            "modelstudio",
            "dashscope",
            "qwencloud",
            "alibaba",
            "alibaba-coding",
            "alibaba-coding-plan",
            "dashscope-coding",
            "modelstudio-api-key",
            "modelstudio-api-key-cn",
            "modelstudio-standard-api-key",
            "modelstudio-standard-api-key-cn",
            "qwen-dashscope",
        ),
        model_prefixes=("qwen/", "modelstudio/", "dashscope/", "qwencloud/"),
        primary_env_names=("QWEN_API_KEY",),
        fallback_env_names=("MODELSTUDIO_API_KEY", "DASHSCOPE_API_KEY", "ALIBABA_CODING_PLAN_API_KEY"),
    ),
    OfficialProviderSpec(
        family="stepfun-plan",
        service="StepFun Plan",
        provider_name="publisher_stepfun_plan_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://api.stepfun.ai/step_plan/v1",
        markers=("stepfun-plan", "step-fun-plan", "stepfun-coding-plan"),
        model_prefixes=("stepfun-plan/",),
        primary_env_names=("STEPFUN_API_KEY",),
    ),
    OfficialProviderSpec(
        family="tencent-tokenhub",
        service="Tencent TokenHub",
        provider_name="publisher_tencent_tokenhub_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://tokenhub.tencentmaas.com/v1",
        markers=("tencent-tokenhub", "tokenhub", "tencent", "tencent-cloud", "tencentmaas", "tencent-maas"),
        model_prefixes=("tencent-tokenhub/",),
        primary_env_names=("TOKENHUB_API_KEY",),
    ),
    OfficialProviderSpec(
        family="xiaomi",
        service="Xiaomi MiMo",
        provider_name="publisher_xiaomi_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://api.xiaomimimo.com/v1",
        markers=("xiaomi", "mimo", "xiaomi-mimo"),
        model_prefixes=("xiaomi/",),
        primary_env_names=("XIAOMI_API_KEY",),
    ),
    OfficialProviderSpec(
        family="byteplus-plan",
        service="BytePlus Coding Plan",
        provider_name="publisher_byteplus_plan_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://ark.ap-southeast.bytepluses.com/api/coding/v3",
        markers=("byteplus-plan", "byteplus-coding-plan"),
        model_prefixes=("byteplus-plan/",),
        primary_env_names=("BYTEPLUS_API_KEY",),
    ),
    OfficialProviderSpec(
        family="byteplus",
        service="BytePlus",
        provider_name="publisher_byteplus_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://ark.ap-southeast.bytepluses.com/api/v3",
        markers=("byteplus",),
        model_prefixes=("byteplus/",),
        primary_env_names=("BYTEPLUS_API_KEY",),
    ),
    OfficialProviderSpec(
        family="cerebras",
        service="Cerebras",
        provider_name="publisher_cerebras_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://api.cerebras.ai/v1",
        markers=("cerebras",),
        model_prefixes=("cerebras/",),
        primary_env_names=("CEREBRAS_API_KEY",),
    ),
    OfficialProviderSpec(
        family="chutes",
        service="Chutes",
        provider_name="publisher_chutes_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://llm.chutes.ai/v1",
        markers=("chutes",),
        model_prefixes=("chutes/",),
        primary_env_names=("CHUTES_API_KEY",),
        fallback_env_names=("CHUTES_OAUTH_TOKEN",),
    ),
    OfficialProviderSpec(
        family="cohere",
        service="Cohere",
        provider_name="publisher_cohere_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://api.cohere.ai/compatibility/v1",
        markers=("cohere",),
        model_prefixes=("cohere/",),
        primary_env_names=("COHERE_API_KEY",),
    ),
    OfficialProviderSpec(
        family="deepinfra",
        service="DeepInfra",
        provider_name="publisher_deepinfra_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://api.deepinfra.com/v1/openai",
        markers=("deepinfra", "deep-infra"),
        model_prefixes=("deepinfra/",),
        primary_env_names=("DEEPINFRA_API_KEY",),
    ),
    OfficialProviderSpec(
        family="fireworks",
        service="Fireworks",
        provider_name="publisher_fireworks_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://api.fireworks.ai/inference/v1",
        markers=("fireworks", "fireworks-ai"),
        model_prefixes=("fireworks/",),
        primary_env_names=("FIREWORKS_API_KEY",),
    ),
    OfficialProviderSpec(
        family="groq",
        service="Groq",
        provider_name="publisher_groq_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://api.groq.com/openai/v1",
        markers=("groq",),
        model_prefixes=("groq/",),
        primary_env_names=("GROQ_API_KEY",),
    ),
    OfficialProviderSpec(
        family="mistral",
        service="Mistral",
        provider_name="publisher_mistral_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://api.mistral.ai/v1",
        markers=("mistral",),
        model_prefixes=("mistral/",),
        primary_env_names=("MISTRAL_API_KEY",),
    ),
    OfficialProviderSpec(
        family="qianfan",
        service="Baidu Qianfan",
        provider_name="publisher_qianfan_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://qianfan.baidubce.com/v2",
        markers=("qianfan", "baidu-qianfan"),
        model_prefixes=("qianfan/",),
        primary_env_names=("QIANFAN_API_KEY",),
    ),
    OfficialProviderSpec(
        family="qwen-oauth",
        service="Qwen Portal",
        provider_name="publisher_qwen_oauth_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://portal.qwen.ai/v1",
        markers=("qwen-oauth", "qwen-portal", "qwen-cli"),
        model_prefixes=("qwen-oauth/", "qwen-portal/", "qwen-cli/"),
        primary_env_names=("QWEN_API_KEY",),
    ),
    OfficialProviderSpec(
        family="stepfun",
        service="StepFun",
        provider_name="publisher_stepfun_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://api.stepfun.ai/v1",
        markers=("stepfun", "step-fun"),
        model_prefixes=("stepfun/",),
        primary_env_names=("STEPFUN_API_KEY",),
    ),
    OfficialProviderSpec(
        family="together",
        service="Together AI",
        provider_name="publisher_together_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://api.together.xyz/v1",
        markers=("together", "together-ai"),
        model_prefixes=("together/",),
        primary_env_names=("TOGETHER_API_KEY",),
    ),
    OfficialProviderSpec(
        family="venice",
        service="Venice",
        provider_name="publisher_venice_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://api.venice.ai/api/v1",
        markers=("venice", "venice-ai"),
        model_prefixes=("venice/",),
        primary_env_names=("VENICE_API_KEY",),
    ),
    OfficialProviderSpec(
        family="volcengine-plan",
        service="Volcano Engine Coding Plan",
        provider_name="publisher_volcengine_plan_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
        markers=("volcengine-plan", "volcano-engine-plan", "doubao-plan"),
        model_prefixes=("volcengine-plan/",),
        primary_env_names=("VOLCANO_ENGINE_API_KEY",),
    ),
    OfficialProviderSpec(
        family="volcengine",
        service="Volcano Engine",
        provider_name="publisher_volcengine_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        markers=("volcengine", "volcano-engine", "doubao"),
        model_prefixes=("volcengine/",),
        primary_env_names=("VOLCANO_ENGINE_API_KEY",),
    ),
    OfficialProviderSpec(
        family="xiaomi-token-plan",
        service="Xiaomi MiMo Token Plan",
        provider_name="publisher_xiaomi_token_plan_official",
        api=PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
        base_url="https://token-plan-sgp.xiaomimimo.com/v1",
        markers=("xiaomi-token-plan", "mimo-token-plan"),
        model_prefixes=("xiaomi-token-plan/",),
        primary_env_names=("XIAOMI_TOKEN_PLAN_API_KEY",),
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


def build_official_provider_specs(
    families: Collection[str],
    *,
    overrides: Optional[Mapping[str, OfficialProviderSpecOverride]] = None,
    specs: tuple[OfficialProviderSpec, ...] = ALL_OFFICIAL_PROVIDER_SPECS,
) -> tuple[OfficialProviderSpec, ...]:
    family_names = set(families)
    selected = tuple(spec for spec in specs if spec.family in family_names)
    if not overrides:
        _validate_official_provider_api_formats(selected)
        return selected
    selected = _apply_official_provider_overrides(selected, overrides)
    _validate_official_provider_api_formats(selected)
    return selected


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


def find_official_provider_by_base_url(
    value: str,
    *,
    specs: tuple[OfficialProviderSpec, ...] = ALL_OFFICIAL_PROVIDER_SPECS,
) -> Optional[OfficialProviderSpec]:
    normalized = str(value or "").strip().rstrip("/")
    if not normalized:
        return None
    for spec in specs:
        if normalized == spec.base_url.rstrip("/"):
            return spec
    return None


__all__ = [
    "ALL_OFFICIAL_PROVIDER_SPECS",
    "ALL_OFFICIAL_PROVIDER_SPECS_BY_FAMILY",
    "ALL_OFFICIAL_PROVIDER_SPECS_BY_NAME",
    "OfficialProviderSpec",
    "OfficialProviderSpecOverride",
    "build_official_provider_specs",
    "find_official_provider_by_base_url",
    "find_official_provider_by_marker",
    "find_official_provider_in_text",
    "match_official_builtin_model_provider",
]
