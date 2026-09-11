from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from packaging.common.constants import OPENAI_OFFICIAL_URL_V1
from packaging.common.text_parse import looks_like_platform_managed_placeholder_value
from packaging.common.url_values import normalize_http_url_candidate
from packaging.config.toml_loader import safe_toml_loads, tomllib
from packaging.runtime.llm.api_formats import PLATFORM_API_FORMAT_OPENAI_RESPONSES
from packaging.runtime.llm.official_providers import (
    OfficialProviderSpec,
    find_official_provider_by_base_url,
    find_official_provider_by_marker,
)
from packaging.runtime.contracts import FieldLocation, LlmRoute, SourceKind
from packaging.runtime.contracts import RuntimeContract, ScanContext, build_llm_route
from packaging.runtime.plugins.codex.home import resolve_codex_home
from packaging.runtime.plugins.support import invalid_text_config_error, usable_process_env_value


CONFIG_RELPATH = ".codex/config.toml"
CODEX_AUTH_PROVIDER_NAME = "publisher_openai_official"
DEFAULT_CODEX_API_FORMAT = PLATFORM_API_FORMAT_OPENAI_RESPONSES
CODEX_DEFAULT_API_KEY_FIELD = "OPENAI_API_KEY"
CODEX_WIRE_API_FORMATS = {
    "responses": PLATFORM_API_FORMAT_OPENAI_RESPONSES,
}


@dataclass(frozen=True)
class CodexProviderState:
    selected_provider: str
    provider_exists: bool
    base_url: str
    base_url_field: str
    base_url_toml_section: str
    model: str
    api_format: str


def api_format_for_wire_api(value: object) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return DEFAULT_CODEX_API_FORMAT
    try:
        return CODEX_WIRE_API_FORMATS[normalized]
    except KeyError as exc:
        supported = ", ".join(sorted(CODEX_WIRE_API_FORMATS))
        raise ValueError(
            f'unsupported Codex wire_api="{normalized}"; supported values: {supported}'
        ) from exc


def _api_format_for_provider_section(section: dict[str, Any]) -> str:
    if "wire_api" not in section:
        return DEFAULT_CODEX_API_FORMAT
    return api_format_for_wire_api(section.get("wire_api", ""))


def validate_codex_provider_capability(
    *,
    api_format: object,
    provider_name: object = "",
    base_url: object = "",
) -> None:
    normalized_api_format = str(api_format or "").strip()
    if normalized_api_format != PLATFORM_API_FORMAT_OPENAI_RESPONSES:
        raise ValueError(
            'Codex only supports api_format="openai-responses"; '
            f'got "{normalized_api_format or "<empty>"}"'
        )

    provider_spec = find_official_provider_by_marker(str(provider_name or "").strip())
    if provider_spec is not None:
        _require_responses_official_provider(provider_spec, matched_by="provider_name")

    url_spec = find_official_provider_by_base_url(str(base_url or "").strip())
    if url_spec is not None:
        _require_responses_official_provider(url_spec, matched_by="base_url")


def _require_responses_official_provider(
    spec: OfficialProviderSpec,
    *,
    matched_by: str,
) -> None:
    if spec.api == PLATFORM_API_FORMAT_OPENAI_RESPONSES:
        return
    raise ValueError(
        f'Codex does not support official provider "{spec.provider_name}" matched by {matched_by}; '
        f'its api_format is "{spec.api}", but Codex requires "{PLATFORM_API_FORMAT_OPENAI_RESPONSES}"'
    )


def load_codex_config_state_from_text(text: str) -> Optional[CodexProviderState]:
    try:
        payload = safe_toml_loads(str(text or ""))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(str(exc)) from exc
    if not isinstance(payload, dict):
        raise ValueError("root value is not a TOML table")
    _validate_provider_sections(payload)
    return _provider_state_from_payload(payload)


def _load_codex_provider_state(config_path: Path) -> Optional[CodexProviderState]:
    if not config_path.is_file():
        return None
    try:
        text = config_path.read_text(encoding="utf-8")
        return load_codex_config_state_from_text(text)
    except (OSError, ValueError) as exc:
        raise invalid_text_config_error(
            "Codex config",
            "TOML",
            CONFIG_RELPATH,
            str(exc),
        ) from exc


def _validate_provider_sections(payload: dict[str, Any]) -> None:
    sections = payload.get("model_providers")
    if not isinstance(sections, dict):
        return
    for provider_name, section in sections.items():
        if not isinstance(section, dict):
            continue
        try:
            validate_codex_provider_capability(
                api_format=_api_format_for_provider_section(section),
                provider_name=provider_name,
                base_url=section.get("base_url", ""),
            )
        except ValueError as exc:
            raise ValueError(f'invalid Codex model provider "{provider_name}": {exc}') from exc


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
                provider_exists=True,
                base_url=top_level_base_url,
                base_url_field="openai_base_url" if top_level_base_url else "",
                base_url_toml_section="",
                model=model,
                api_format=DEFAULT_CODEX_API_FORMAT,
            )
        if explicit:
            return CodexProviderState(
                selected_provider=selected,
                provider_exists=False,
                base_url="",
                base_url_field="",
                base_url_toml_section="",
                model=model,
                api_format=DEFAULT_CODEX_API_FORMAT,
            )

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
    return CodexProviderState(
        selected_provider=selected,
        provider_exists=True,
        base_url=base_url,
        base_url_field=base_url_field,
        base_url_toml_section=base_url_toml_section,
        model=model,
        api_format=_api_format_for_provider_section(section),
    )


def _normalized_top_level_openai_base_url(payload: dict[str, Any]) -> str:
    value = payload.get("openai_base_url")
    if not isinstance(value, str) or not value.strip():
        return ""
    normalized = normalize_http_url_candidate(value)
    if not normalized or looks_like_platform_managed_placeholder_value(value):
        return ""
    return normalized


def _scan_provider_metadata(ctx: ScanContext, config_path: Path) -> list[LlmRoute]:
    state = _load_codex_provider_state(config_path)
    provider_name = state.selected_provider if state is not None else CODEX_AUTH_PROVIDER_NAME
    if state is not None and not state.provider_exists:
        return []

    configured_url = state.base_url if state is not None else ""
    process_url = ""
    if not configured_url and provider_name == CODEX_AUTH_PROVIDER_NAME:
        process_url = normalize_http_url_candidate(
            usable_process_env_value(ctx.process_env, "OPENAI_BASE_URL")
        )
    resolved_url = configured_url or process_url
    if not resolved_url and provider_name == CODEX_AUTH_PROVIDER_NAME:
        resolved_url = OPENAI_OFFICIAL_URL_V1
    if not resolved_url:
        return []

    api_format = state.api_format if state is not None else DEFAULT_CODEX_API_FORMAT
    validate_codex_provider_capability(
        api_format=api_format,
        provider_name=provider_name,
        base_url=resolved_url,
    )
    source_kind = (
        SourceKind.FILE
        if configured_url
        else SourceKind.PROCESS_ENV
        if process_url
        else SourceKind.SYNTHESIZED
    )
    location = (
        FieldLocation(fmt="toml", toml_section=state.base_url_toml_section)
        if configured_url and state is not None
        else None
    )
    return [
        build_llm_route(
            service="OpenAI",
            group=f"{CONFIG_RELPATH}#model_providers.{provider_name}",
            url=resolved_url,
            url_field=(
                state.base_url_field
                if state is not None and state.base_url_field
                else "OPENAI_BASE_URL"
            ),
            source_relpath=CONFIG_RELPATH,
            source_kind=source_kind,
            location=location,
            model=state.model if state is not None else "",
            api_format=api_format,
            provider_name=provider_name,
            api_key_field=CODEX_DEFAULT_API_KEY_FIELD,
        )
    ]


class CodexRuntime(RuntimeContract):
    def os_fallback_environment_names(self) -> frozenset[str]:
        return frozenset({"OPENAI_BASE_URL"})

    def routes(self, ctx: ScanContext) -> list[LlmRoute]:
        codex_home = resolve_codex_home(home=ctx.user_home)
        return _scan_provider_metadata(ctx, codex_home / "config.toml")


__all__ = [
    "CodexRuntime",
    "api_format_for_wire_api",
    "load_codex_config_state_from_text",
    "validate_codex_provider_capability",
]
