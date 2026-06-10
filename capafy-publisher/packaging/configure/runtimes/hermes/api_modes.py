from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlparse

from packaging._shared.common.url_values import normalize_http_url_candidate
from packaging._shared.llm.api_formats import (
    DEFAULT_PLATFORM_API_FORMAT,
    PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES,
    PLATFORM_API_FORMAT_GOOGLE_GENERATIVE_AI,
    PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
    PLATFORM_API_FORMAT_OPENAI_RESPONSES,
)
from packaging._shared.llm.official_providers import OfficialProviderSpec


_HERMES_API_MODE_BY_PLATFORM_API = {
    PLATFORM_API_FORMAT_OPENAI_COMPLETIONS: "chat_completions",
    PLATFORM_API_FORMAT_OPENAI_RESPONSES: "codex_responses",
    PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES: "anthropic_messages",
    PLATFORM_API_FORMAT_GOOGLE_GENERATIVE_AI: "chat_completions",
}
_PLATFORM_API_BY_HERMES_API_MODE = {
    "chat_completions": PLATFORM_API_FORMAT_OPENAI_COMPLETIONS,
    "codex_responses": PLATFORM_API_FORMAT_OPENAI_RESPONSES,
    "anthropic_messages": PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES,
}


def hermes_api_mode_for_config(value: object) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    return _HERMES_API_MODE_BY_PLATFORM_API.get(normalized, normalized)


def platform_api_format_for_upload(value: object) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    return _PLATFORM_API_BY_HERMES_API_MODE.get(normalized, normalized)


def hermes_default_api_mode(spec: Optional[OfficialProviderSpec]) -> str:
    if spec is None:
        return hermes_api_mode_for_config(DEFAULT_PLATFORM_API_FORMAT)
    return hermes_api_mode_for_config(spec.api)


def platform_default_api_format(spec: Optional[OfficialProviderSpec]) -> str:
    return platform_api_format_for_upload(hermes_default_api_mode(spec)) or DEFAULT_PLATFORM_API_FORMAT


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
    if path.endswith("/anthropic"):
        return hermes_api_mode_for_config(PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES)
    if host == "api.kimi.com" and "/coding" in normalized.lower():
        return hermes_api_mode_for_config(PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES)
    return ""


def hermes_api_mode_from_block_url(block: dict[str, Any]) -> str:
    return hermes_api_mode_from_url(block.get("base_url"))


def hermes_api_mode_from_block(block: dict[str, Any], spec: Optional[OfficialProviderSpec]) -> str:
    value = hermes_api_mode_for_config(block.get("api_mode"))
    if value:
        return value
    value = hermes_api_mode_from_block_url(block)
    if value:
        return value
    return hermes_default_api_mode(spec)


def platform_api_format_from_block(block: dict[str, Any], spec: Optional[OfficialProviderSpec]) -> str:
    value = platform_api_format_for_upload(block.get("api_mode"))
    if value:
        return value
    value = hermes_api_mode_from_block_url(block)
    if value:
        return platform_api_format_for_upload(value)
    return platform_default_api_format(spec)


__all__ = [
    "hermes_api_mode_from_block",
    "hermes_api_mode_from_block_url",
    "hermes_api_mode_from_url",
    "hermes_default_api_mode",
    "hermes_api_mode_for_config",
    "platform_api_format_for_upload",
    "platform_api_format_from_block",
    "platform_default_api_format",
]
