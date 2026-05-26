from __future__ import annotations

from typing import Mapping

from packaging._shared.common.url_values import normalize_http_url_candidate
from packaging.configure.candidate import Candidate
from packaging.configure.contracts import SourceKind
from packaging.configure.env_values import usable_process_env_value


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
        if selected_provider_blocked:
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
    if selected_provider_blocked:
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
    if selected_provider_blocked:
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
    "codex_login_state_candidates",
    "codex_platform_key_mode_candidate",
    "official_process_env_fallback_candidates",
    "should_build_codex_platform_key_mode",
]
