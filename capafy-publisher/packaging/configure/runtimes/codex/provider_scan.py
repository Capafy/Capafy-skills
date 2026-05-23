from __future__ import annotations

from typing import Any

from packaging._shared.common.toml_loader import safe_toml_loads, tomllib
from packaging._shared.common.url_values import normalize_http_url_candidate
from packaging.configure.candidate import Candidate
from packaging.configure.contracts import FieldLocation, SourceKind
from packaging.configure.runtimes.codex.auth import CODEX_AUTH_PROVIDER_NAME
from packaging.configure.sensitive.literals import looks_like_platform_managed_placeholder_value
from packaging.configure.url_proxy.base import ScanContext


_CONFIG_RELPATH = ".codex/config.toml"
_CODEX_WIRE_API_FORMATS = {
    "chat": "openai-completions",
    "responses": "openai-responses",
}


def api_format_for_wire_api(value: object) -> str:
    normalized = str(value or "").strip()
    return _CODEX_WIRE_API_FORMATS.get(normalized, "openai-responses")


def api_format_for_codex_provider_section(section: dict[str, Any]) -> str:
    if "wire_api" not in section:
        return "openai-responses"
    return api_format_for_wire_api(section.get("wire_api", ""))


def load_codex_config_payload(ctx: ScanContext) -> dict[str, Any]:
    file_path = ctx.staging_root / _CONFIG_RELPATH
    if not file_path.is_file():
        return {}
    try:
        payload = safe_toml_loads(file_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def codex_config_metadata(ctx: ScanContext) -> dict[str, Any]:
    payload = load_codex_config_payload(ctx)
    if not payload:
        return {}
    model = str(payload.get("model", "") or "").strip()
    provider_metadata: dict[str, dict[str, str]] = {}
    sections = payload.get("model_providers")
    if isinstance(sections, dict):
        for name, section in sections.items():
            if not isinstance(section, dict):
                continue
            api_format = api_format_for_codex_provider_section(section)
            provider_metadata[str(name)] = {
                "model": model,
                "api_format": api_format,
            }
    return {
        "model": model,
        "default_api_format": "openai-responses",
        "providers": provider_metadata,
    }


def scan_toml_providers(ctx: ScanContext, out_env_keys: set[str]) -> list[Candidate]:
    payload = load_codex_config_payload(ctx)
    if not payload:
        return []

    sections = payload.get("model_providers")
    selected = str(payload.get("model_provider", "")).strip()
    top_level_model = str(payload.get("model", "") or "").strip()
    candidates: list[Candidate] = []
    top_level_openai_url = payload.get("openai_base_url")
    if isinstance(top_level_openai_url, str) and top_level_openai_url.strip():
        normalized_url = normalize_http_url_candidate(top_level_openai_url)
        if normalized_url and not looks_like_platform_managed_placeholder_value(top_level_openai_url):
            candidates.append(Candidate(
                role="base_url",
                field="openai_base_url",
                value=normalized_url,
                source_kind=SourceKind.FILE,
                source_relpath=_CONFIG_RELPATH,
                location=FieldLocation(fmt="toml", toml_section=""),
                extra={
                    "provider_name": CODEX_AUTH_PROVIDER_NAME,
                    "top_level_openai_base_url": True,
                    "model": top_level_model,
                    "api_format": "openai-responses",
                },
            ))

    if isinstance(sections, dict):
        for name, section in sections.items():
            if not isinstance(section, dict):
                continue
            api_format = api_format_for_codex_provider_section(section)
            env_key = str(section.get("env_key", "")).strip()
            if env_key:
                out_env_keys.add(env_key)
                value = str(ctx.process_env.get(env_key, "")).strip()
                if looks_like_platform_managed_placeholder_value(value):
                    value = ""
                candidates.append(Candidate(
                    role="api_key",
                    field=env_key,
                    value=value,
                    source_kind=SourceKind.PROCESS_ENV,
                    source_relpath=_CONFIG_RELPATH,
                    location=FieldLocation(fmt="toml", toml_section=f"model_providers.{name}"),
                    extra={
                        "provider_name": name,
                        "env_key_reference": True,
                        "selected_provider": name == selected,
                        "model": top_level_model,
                        "api_format": api_format,
                    },
                ))
            url_value = section.get("base_url")
            if isinstance(url_value, str) and url_value.strip():
                normalized_url = normalize_http_url_candidate(url_value)
                if not normalized_url or looks_like_platform_managed_placeholder_value(url_value):
                    continue
                candidates.append(Candidate(
                    role="base_url",
                    field="base_url",
                    value=normalized_url,
                    source_kind=SourceKind.FILE,
                    source_relpath=_CONFIG_RELPATH,
                    location=FieldLocation(fmt="toml", toml_section=f"model_providers.{name}"),
                    extra={
                        "provider_name": name,
                        "model": top_level_model,
                        "api_format": api_format,
                    },
                ))
    return candidates


__all__ = [
    "api_format_for_codex_provider_section",
    "api_format_for_wire_api",
    "codex_config_metadata",
    "load_codex_config_payload",
    "scan_toml_providers",
]
