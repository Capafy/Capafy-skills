from __future__ import annotations

from typing import Optional

from packaging.configure.candidate import Candidate
from packaging.configure.contracts import FieldLocation, SourceKind
from packaging.configure.env_values import usable_process_env_value
from packaging.configure.runtimes.codex.config_state import (
    CONFIG_RELPATH,
    load_codex_config_state,
)
from packaging.configure.url_proxy.base import ScanContext


def scan_toml_providers(ctx: ScanContext, out_env_keys: set[str]) -> list[Candidate]:
    config_state = load_codex_config_state(ctx.staging_root / CONFIG_RELPATH)
    if config_state.exists and config_state.parse_failed:
        return [_codex_provider_marker(provider_name="", provider_exists=False)]
    state = config_state.provider
    if state is None:
        return []

    if state.env_key:
        out_env_keys.add(state.env_key)
    candidates: list[Candidate] = []
    common_extra = {
        "codex_provider_state": True,
        "provider_name": state.selected_provider,
        "selected_provider": True,
        "explicit_model_provider": state.explicit_model_provider,
        "provider_exists": state.provider_exists,
        "model": state.model,
        "api_format": state.api_format,
    }
    if not state.provider_exists:
        candidates.append(_codex_provider_marker(
            provider_name=state.selected_provider,
            provider_exists=False,
            extra=common_extra,
        ))
        return candidates
    if state.env_key:
        value = usable_process_env_value(ctx.process_env, state.env_key)
        candidates.append(Candidate(
            role="api_key",
            field=state.env_key,
            value=value,
            source_kind=SourceKind.PROCESS_ENV,
            source_relpath=CONFIG_RELPATH,
            location=FieldLocation(fmt="toml", toml_section=f"model_providers.{state.selected_provider}"),
            extra={
                **common_extra,
                "env_key_reference": state.configured_env_key,
                "default_env_key": not state.configured_env_key,
            },
        ))
    if state.base_url:
        candidates.append(Candidate(
            role="base_url",
            field=state.base_url_field or "base_url",
            value=state.base_url,
            source_kind=SourceKind.FILE,
            source_relpath=CONFIG_RELPATH,
            location=FieldLocation(fmt="toml", toml_section=state.base_url_toml_section),
            extra=common_extra,
        ))
    return candidates


def _codex_provider_marker(
    *,
    provider_name: str,
    provider_exists: bool,
    extra: Optional[dict] = None,
) -> Candidate:
    return Candidate(
        role="url_proxy_group",
        field="model_provider",
        value=str(provider_name or "").strip(),
        source_kind=SourceKind.FILE,
        source_relpath=CONFIG_RELPATH,
        location=FieldLocation(fmt="toml"),
        extra={
            "codex_provider_state": True,
            "provider_name": str(provider_name or "").strip(),
            "provider_exists": provider_exists,
            **(extra or {}),
        },
    )


__all__ = [
    "scan_toml_providers",
]
