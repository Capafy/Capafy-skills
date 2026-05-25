from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from packaging._shared.common.toml_loader import safe_toml_loads, tomllib
from packaging._shared.common.url_values import normalize_http_url_candidate
from packaging.configure.runtimes.codex.auth import CODEX_AUTH_ENV_KEY, CODEX_AUTH_PROVIDER_NAME
from packaging.configure.sensitive.literals import looks_like_platform_managed_placeholder_value


CONFIG_RELPATH = ".codex/config.toml"
DEFAULT_CODEX_API_FORMAT = "openai-responses"
_CODEX_WIRE_API_FORMATS = {
    "chat": "openai-completions",
    "responses": DEFAULT_CODEX_API_FORMAT,
}


@dataclass(frozen=True)
class CodexProviderState:
    selected_provider: str
    explicit_model_provider: bool
    provider_exists: bool
    env_key: str
    configured_env_key: bool
    base_url: str
    base_url_field: str
    base_url_toml_section: str
    model: str
    api_format: str


@dataclass(frozen=True)
class CodexConfigState:
    exists: bool
    parse_failed: bool
    payload: dict[str, Any]
    provider: Optional[CodexProviderState]


def api_format_for_wire_api(value: object) -> str:
    normalized = str(value or "").strip()
    return _CODEX_WIRE_API_FORMATS.get(normalized, DEFAULT_CODEX_API_FORMAT)


def api_format_for_codex_provider_section(section: dict[str, Any]) -> str:
    if "wire_api" not in section:
        return DEFAULT_CODEX_API_FORMAT
    return api_format_for_wire_api(section.get("wire_api", ""))


def load_codex_config_state(config_path: Path) -> CodexConfigState:
    if not config_path.is_file():
        return CodexConfigState(False, False, {}, None)
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError:
        return CodexConfigState(True, True, {}, None)
    return load_codex_config_state_from_text(text, exists=True)


def load_codex_config_state_from_text(text: str, *, exists: bool = True) -> CodexConfigState:
    try:
        payload = safe_toml_loads(str(text or ""))
    except tomllib.TOMLDecodeError:
        return CodexConfigState(exists, True, {}, None)
    if not isinstance(payload, dict):
        return CodexConfigState(exists, True, {}, None)
    return CodexConfigState(
        exists=exists,
        parse_failed=False,
        payload=payload,
        provider=_provider_state_from_payload(payload),
    )


def _provider_state_from_payload(payload: dict[str, Any]) -> Optional[CodexProviderState]:
    if not payload:
        return None
    selected = str(payload.get("model_provider", "") or "").strip() or CODEX_AUTH_PROVIDER_NAME
    explicit = bool(str(payload.get("model_provider", "") or "").strip())
    model = str(payload.get("model", "") or "").strip()
    top_level_base_url = _normalized_top_level_openai_base_url(payload)
    sections = payload.get("model_providers")
    section = sections.get(selected) if isinstance(sections, dict) else None
    if not isinstance(section, dict):
        if selected == CODEX_AUTH_PROVIDER_NAME:
            return CodexProviderState(
                selected_provider=CODEX_AUTH_PROVIDER_NAME,
                explicit_model_provider=explicit,
                provider_exists=True,
                env_key=CODEX_AUTH_ENV_KEY,
                configured_env_key=False,
                base_url=top_level_base_url,
                base_url_field="openai_base_url" if top_level_base_url else "",
                base_url_toml_section="",
                model=model,
                api_format=DEFAULT_CODEX_API_FORMAT,
            )
        if explicit:
            return CodexProviderState(
                selected_provider=selected,
                explicit_model_provider=True,
                provider_exists=False,
                env_key="",
                configured_env_key=False,
                base_url="",
                base_url_field="",
                base_url_toml_section="",
                model=model,
                api_format=DEFAULT_CODEX_API_FORMAT,
            )

    configured_env_key = str(section.get("env_key", "") or "").strip()
    env_key = configured_env_key or CODEX_AUTH_ENV_KEY
    raw_base_url = section.get("base_url")
    base_url = ""
    base_url_field = ""
    base_url_toml_section = ""
    if isinstance(raw_base_url, str) and raw_base_url.strip():
        normalized_url = normalize_http_url_candidate(raw_base_url)
        if normalized_url and not looks_like_platform_managed_placeholder_value(raw_base_url):
            base_url = normalized_url
            base_url_field = "base_url"
            base_url_toml_section = f"model_providers.{selected}"
    if not base_url and selected == CODEX_AUTH_PROVIDER_NAME and top_level_base_url:
        base_url = top_level_base_url
        base_url_field = "openai_base_url"
        base_url_toml_section = ""
    return CodexProviderState(
        selected_provider=selected,
        explicit_model_provider=explicit,
        provider_exists=True,
        env_key=env_key,
        configured_env_key=bool(configured_env_key),
        base_url=base_url,
        base_url_field=base_url_field,
        base_url_toml_section=base_url_toml_section,
        model=model,
        api_format=api_format_for_codex_provider_section(section),
    )


def _normalized_top_level_openai_base_url(payload: dict[str, Any]) -> str:
    value = payload.get("openai_base_url")
    if not isinstance(value, str) or not value.strip():
        return ""
    normalized = normalize_http_url_candidate(value)
    if not normalized or looks_like_platform_managed_placeholder_value(value):
        return ""
    return normalized


__all__ = [
    "CONFIG_RELPATH",
    "DEFAULT_CODEX_API_FORMAT",
    "CodexConfigState",
    "CodexProviderState",
    "api_format_for_codex_provider_section",
    "api_format_for_wire_api",
    "load_codex_config_state",
    "load_codex_config_state_from_text",
]
