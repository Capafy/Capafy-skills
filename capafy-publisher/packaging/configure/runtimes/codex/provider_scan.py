from __future__ import annotations

from pathlib import Path

from packaging._shared.common.constants import OPENAI_OFFICIAL_URL_V1
from packaging._shared.common.url_values import normalize_http_url_candidate
from packaging.configure.candidate import Candidate
from packaging.configure.config_errors import invalid_text_config_error
from packaging.configure.contracts import FieldLocation, SourceKind
from packaging.configure.env_values import usable_process_env_value
from packaging.configure.runtimes.codex.auth import CODEX_AUTH_ENV_KEY, CODEX_AUTH_PROVIDER_NAME
from packaging.configure.runtimes.codex.config_state import (
    CONFIG_RELPATH,
    DEFAULT_CODEX_API_FORMAT,
    load_codex_config_state,
)
from packaging.configure.url_proxy.base import ScanContext


def scan_provider_metadata(ctx: ScanContext, config_path: Path) -> list[Candidate]:
    """Read Codex routing metadata without collecting any local API key value."""
    try:
        config_state = load_codex_config_state(config_path)
    except ValueError as exc:
        raise invalid_text_config_error(
            "Codex config",
            "TOML",
            CONFIG_RELPATH,
            str(exc),
        ) from exc
    if config_state.exists and config_state.parse_failed:
        raise invalid_text_config_error(
            "Codex config",
            "TOML",
            CONFIG_RELPATH,
            config_state.parse_error,
        )

    state = config_state.provider
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

    model = state.model if state is not None else ""
    api_format = state.api_format if state is not None else DEFAULT_CODEX_API_FORMAT
    key_field = state.env_key if state is not None and state.env_key else CODEX_AUTH_ENV_KEY
    common_extra = {
        "codex_provider_state": True,
        "provider_name": provider_name,
        "model": model,
        "api_format": api_format,
    }
    key_candidate = Candidate(
        role="synthesized_api_key",
        field=key_field,
        value="",
        source_kind=SourceKind.SYNTHESIZED,
        source_relpath="",
        extra=common_extra,
    )
    if configured_url:
        url_source_kind = SourceKind.FILE
        url_location = FieldLocation(
            fmt="toml",
            toml_section=(state.base_url_toml_section if state is not None else ""),
        )
    elif process_url:
        url_source_kind = SourceKind.PROCESS_ENV
        url_location = None
    else:
        url_source_kind = SourceKind.SYNTHESIZED
        url_location = None
    url_candidate = Candidate(
        role="base_url",
        field=(state.base_url_field if state is not None and state.base_url_field else "OPENAI_BASE_URL"),
        value=resolved_url,
        source_kind=url_source_kind,
        source_relpath=CONFIG_RELPATH,
        location=url_location,
        extra=common_extra,
    )
    return [key_candidate, url_candidate]


__all__ = ["scan_provider_metadata"]
