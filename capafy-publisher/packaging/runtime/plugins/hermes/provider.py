from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlparse

from packaging.common.url_values import normalize_http_url_candidate
from packaging.runtime.llm.api_formats import (
    DEFAULT_PLATFORM_API_FORMAT,
    PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES,
    PLATFORM_API_FORMAT_GOOGLE_GENERATIVE_AI,
    PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
    PLATFORM_API_FORMAT_OPENAI_RESPONSES,
    SUPPORTED_PLATFORM_API_FORMATS,
    is_supported_platform_api_format,
)
from packaging.runtime.llm.official_providers import (
    OfficialProviderSpec as HermesOfficialProviderSpec,
    build_platform_official_provider_specs,
    find_official_provider_by_base_url,
    find_official_provider_by_env_name,
    find_official_provider_by_marker,
)
from packaging.runtime.plugins.support import env_reference_name


_HERMES_API_MODE_BY_PLATFORM_API = {
    PLATFORM_API_FORMAT_OPENAI_COMPLETIONS: "chat_completions",
    PLATFORM_API_FORMAT_OPENAI_RESPONSES: "codex_responses",
    PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES: "anthropic_messages",
    PLATFORM_API_FORMAT_GOOGLE_GENERATIVE_AI: "chat_completions",
}
_PLATFORM_API_BY_HERMES_API_MODE = {
    "openai_chat": PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
    "chat_completions": PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
    "codex_responses": PLATFORM_API_FORMAT_OPENAI_RESPONSES,
    "anthropic_messages": PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES,
}


HERMES_OFFICIAL_PROVIDER_SPECS = build_platform_official_provider_specs("hermes")


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


def find_hermes_official_provider_by_key_reference(
    value: object,
) -> Optional[HermesOfficialProviderSpec]:
    return find_official_provider_by_env_name(
        env_reference_name(value),
        platform="hermes",
        specs=HERMES_OFFICIAL_PROVIDER_SPECS,
    )


def hermes_api_mode_for_config(value: object) -> str:
    normalized = str(value or "").strip()
    return _HERMES_API_MODE_BY_PLATFORM_API.get(normalized, normalized) if normalized else ""


def platform_api_format_for_upload(value: object) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    mapped = _PLATFORM_API_BY_HERMES_API_MODE.get(normalized, normalized)
    if is_supported_platform_api_format(mapped):
        return mapped
    supported = ", ".join(SUPPORTED_PLATFORM_API_FORMATS)
    raise ValueError(
        f"Unsupported Hermes api_format/api_mode for upload: {normalized}. "
        f"Supported platform api_format values: {supported}"
    )


def hermes_default_api_mode(spec: Optional[HermesOfficialProviderSpec]) -> str:
    return hermes_api_mode_for_config(
        spec.api if spec is not None else DEFAULT_PLATFORM_API_FORMAT
    )


def platform_default_api_format(spec: Optional[HermesOfficialProviderSpec]) -> str:
    return (
        platform_api_format_for_upload(hermes_default_api_mode(spec))
        or DEFAULT_PLATFORM_API_FORMAT
    )


def platform_api_format_for_model(
    spec: Optional[HermesOfficialProviderSpec],
    model: object,
) -> str:
    """Mirror Hermes' model-sensitive OpenCode transport selection."""
    if spec is None or spec.family not in {"opencode-zen", "opencode-go"}:
        return platform_default_api_format(spec)
    normalized = str(model or "").strip().lower()
    prefix = f"{spec.family}/"
    if normalized.startswith(prefix):
        normalized = normalized[len(prefix) :]
    if spec.family == "opencode-go":
        mode = (
            "anthropic_messages"
            if normalized.startswith(("minimax-", "qwen"))
            else "chat_completions"
        )
    elif normalized.startswith("claude-") or normalized.startswith("qwen"):
        mode = "anthropic_messages"
    elif normalized.startswith("gpt-"):
        mode = "codex_responses"
    else:
        mode = "chat_completions"
    return platform_api_format_for_upload(mode)


def hermes_api_mode_from_url(value: object) -> str:
    normalized = normalize_http_url_candidate(str(value or ""))
    if not normalized:
        return ""
    try:
        parsed = urlparse(normalized)
    except ValueError:
        return ""
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/").lower()
    if host in {"api.openai.com", "api.x.ai"}:
        return hermes_api_mode_for_config(PLATFORM_API_FORMAT_OPENAI_RESPONSES)
    if path.endswith("/anthropic") or path.endswith("/anthropic/v1"):
        return hermes_api_mode_for_config(PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES)
    if host == "api.kimi.com" and "/coding" in normalized.lower():
        return hermes_api_mode_for_config(PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES)
    return ""


def hermes_api_mode_from_block_url(block: dict[str, Any]) -> str:
    return hermes_api_mode_from_url(
        block.get("base_url")
        or block.get("api_base")
        or block.get("api")
        or block.get("url")
    )


def platform_api_format_from_block(
    block: dict[str, Any],
    spec: Optional[HermesOfficialProviderSpec],
    *,
    model: object = "",
) -> str:
    if (
        spec is not None
        and spec.family in {"opencode-zen", "opencode-go"}
        and str(model or "").strip()
    ):
        return platform_api_format_for_model(spec, model)
    value = platform_api_format_for_upload(
        block.get("api_mode") or block.get("transport")
    )
    if value:
        if (
            value == PLATFORM_API_FORMAT_OPENAI_COMPLETIONS
            and spec is not None
            and spec.api == PLATFORM_API_FORMAT_GOOGLE_GENERATIVE_AI
        ):
            return spec.api
        return value
    value = hermes_api_mode_from_block_url(block)
    if value:
        return platform_api_format_for_upload(value)
    return platform_default_api_format(spec)


__all__ = [
    "HERMES_OFFICIAL_PROVIDER_SPECS",
    "HermesOfficialProviderSpec",
    "find_hermes_official_provider_by_base_url",
    "find_hermes_official_provider_by_key_reference",
    "find_hermes_official_provider_by_marker",
    "hermes_api_mode_for_config",
    "hermes_api_mode_from_block_url",
    "hermes_api_mode_from_url",
    "hermes_default_api_mode",
    "platform_api_format_for_model",
    "platform_api_format_for_upload",
    "platform_api_format_from_block",
    "platform_default_api_format",
]
