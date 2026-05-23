from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from packaging._shared.common.url_values import normalize_http_url_candidate
from packaging.configure.candidate import Candidate
from packaging.configure.contracts import SourceKind
from packaging.configure.sensitive.literals import looks_like_platform_managed_placeholder_value


def usable_process_env_value(process_env: Mapping[str, str], field: str) -> str:
    value = str(process_env.get(field, "")).strip()
    if looks_like_platform_managed_placeholder_value(value):
        return ""
    return value


def top_level_openai_base_url_candidate(candidates: list[Candidate]) -> Candidate | None:
    return next(
        (
            c for c in candidates
            if c.role == "base_url" and c.extra.get("top_level_openai_base_url")
        ),
        None,
    )


def process_env_openai_base_url_candidate(candidates: list[Candidate]) -> Candidate | None:
    return next(
        (
            c for c in candidates
            if c.role == "base_url"
            and c.source_kind == SourceKind.PROCESS_ENV
            and c.field == "OPENAI_BASE_URL"
        ),
        None,
    )


def has_non_openai_selected_provider(candidates: list[Candidate]) -> bool:
    selected_providers = {
        str(candidate.extra.get("provider_name", "") or "").strip().lower()
        for candidate in candidates
        if candidate.extra.get("selected_provider")
    }
    if not selected_providers:
        return False
    return not any("openai" in provider for provider in selected_providers)


def annotate_candidates_with_config_metadata(
    candidates: list[Candidate],
    metadata: dict[str, Any],
    *,
    official_provider_name: str,
) -> list[Candidate]:
    if not candidates or not metadata:
        return candidates
    updated: list[Candidate] = []
    for candidate in candidates:
        extra = dict(candidate.extra)
        provider = str(extra.get("provider_name", "") or "").strip()
        provider_metadata = metadata.get("providers", {}).get(provider, {}) if provider else {}
        model = str(provider_metadata.get("model", "") or metadata.get("model", "") or "").strip()
        api_format = str(provider_metadata.get("api_format", "") or "").strip()
        if not api_format and (
            candidate.field == "OPENAI_API_KEY"
            or provider == official_provider_name
            or candidate.role == "synthesized_api_key"
            or extra.get("official_process_env_fallback")
        ):
            api_format = str(metadata.get("default_api_format", "") or "").strip()
        if model and "model" not in extra:
            extra["model"] = model
        if api_format and "api_format" not in extra:
            extra["api_format"] = api_format
        updated.append(replace(candidate, extra=extra))
    return updated


def official_process_env_fallback_candidates(
    *,
    config_exists: bool,
    process_env: Mapping[str, str],
    existing_fields: set[str],
    auth_override_env_key: str,
) -> list[Candidate]:
    if not config_exists:
        return []

    candidates: list[Candidate] = []

    api_key = usable_process_env_value(process_env, auth_override_env_key)
    if api_key and "OPENAI_API_KEY" not in existing_fields:
        candidates.append(Candidate(
            role="api_key", field="OPENAI_API_KEY", value=api_key,
            source_kind=SourceKind.PROCESS_ENV, source_relpath=".codex/.env",
            location=None,
            extra={
                "codex_api_key_env_fallback": True,
                "official_process_env_fallback": True,
            },
        ))

    base_url = usable_process_env_value(process_env, "OPENAI_BASE_URL")
    normalized_url = normalize_http_url_candidate(base_url) if base_url else ""
    if normalized_url and "OPENAI_BASE_URL" not in existing_fields:
        candidates.append(Candidate(
            role="base_url", field="OPENAI_BASE_URL", value=normalized_url,
            source_kind=SourceKind.PROCESS_ENV, source_relpath=".codex/config.toml",
            location=None,
            extra={"official_process_env_fallback": True},
        ))
    return candidates


def codex_login_state_candidates(
    *,
    existing: list[Candidate],
    auth_key: str,
    oauth_detected: bool,
    selected_provider_blocked: bool,
    has_local_dotenv_value: bool,
) -> list[Candidate]:
    existing_file_values = {
        str(candidate.value or "").strip()
        for candidate in existing
        if candidate.source_kind == SourceKind.FILE and str(candidate.value or "").strip()
    }
    if auth_key:
        if auth_key in existing_file_values or has_local_dotenv_value:
            return []
        if oauth_detected:
            return []
        if selected_provider_blocked or has_non_openai_selected_provider(existing):
            return []
        return [Candidate(
            role="synthesized_api_key",
            field="OPENAI_API_KEY",
            value=auth_key,
            source_kind=SourceKind.SYNTHESIZED,
            source_relpath=".codex/config.toml",
        )]

    if not oauth_detected:
        return []
    if selected_provider_blocked or has_non_openai_selected_provider(existing):
        return []
    if "OPENAI_API_KEY" not in {c.field for c in existing if c.source_kind == SourceKind.FILE}:
        return [Candidate(
            role="synthesized_api_key",
            field="OPENAI_API_KEY",
            value="",
            source_kind=SourceKind.SYNTHESIZED,
            source_relpath="",
        )]
    return []


def should_build_codex_platform_key_mode(
    *,
    target_id: str,
    existing: list[Candidate],
    selected_provider_blocked: bool,
    auth_key: str,
    has_local_auth_dotenv_value: bool,
) -> bool:
    if target_id != "codex":
        return False
    if selected_provider_blocked or has_non_openai_selected_provider(existing):
        return False
    if any(
        candidate.role in {"api_key", "synthesized_api_key"}
        and str(candidate.value or "").strip()
        for candidate in existing
    ):
        return False
    return not (auth_key and has_local_auth_dotenv_value)


def codex_platform_key_mode_candidate() -> Candidate:
    return Candidate(
        role="synthesized_api_key",
        field="OPENAI_API_KEY",
        value="",
        source_kind=SourceKind.SYNTHESIZED,
        source_relpath="",
    )


__all__ = [
    "annotate_candidates_with_config_metadata",
    "codex_login_state_candidates",
    "codex_platform_key_mode_candidate",
    "has_non_openai_selected_provider",
    "official_process_env_fallback_candidates",
    "process_env_openai_base_url_candidate",
    "should_build_codex_platform_key_mode",
    "top_level_openai_base_url_candidate",
    "usable_process_env_value",
]
