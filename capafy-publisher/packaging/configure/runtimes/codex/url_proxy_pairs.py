from __future__ import annotations

from dataclasses import replace
from typing import Optional

from packaging._shared.common.constants import OPENAI_OFFICIAL_URL_V1
from packaging._shared.common.url_values import build_config_url_proxy_group
from packaging.configure.candidate import Candidate
from packaging.configure.contracts import FieldLocation, SourceKind, UrlProxyPair
from packaging.configure.runtimes.codex.auth import CODEX_AUTH_PROVIDER_NAME
from packaging.configure.runtimes.codex.config_state import DEFAULT_CODEX_API_FORMAT
from packaging.configure.url_proxy.pair_builder import make_pair

REVIEWED_KEY_SOURCE = ".codex/.env"
REVIEWED_URL_SOURCE = ".codex/config.toml"
CODEX_CONTRACT_ID = "codex"
CODEX_SERVICE = "OpenAI"


def provider_group(provider_name: str, source_relpath: str = ".codex/config.toml") -> str:
    return build_config_url_proxy_group(source_relpath, f"model_providers.{provider_name}")


def official_url_candidate(provider: str, source_relpath: str = ".codex/config.toml") -> Candidate:
    return Candidate(
        role="base_url",
        field="OPENAI_BASE_URL",
        value=OPENAI_OFFICIAL_URL_V1,
        source_kind=SourceKind.SYNTHESIZED,
        source_relpath=source_relpath,
        location=FieldLocation(fmt="toml", toml_section=f"model_providers.{provider}"),
    )


def _make_codex_pair(
    *,
    key_candidate: Candidate,
    url_candidate: Candidate,
    group: str,
    model: str = "",
    api_format: str = "",
    is_synthesized: bool = False,
) -> UrlProxyPair:
    return make_pair(
        contract_id=CODEX_CONTRACT_ID,
        service=CODEX_SERVICE,
        key_candidate=key_candidate,
        url_candidate=url_candidate,
        is_synthesized=is_synthesized,
        group=group,
        model=model,
        api_format=api_format or DEFAULT_CODEX_API_FORMAT,
    )


def with_reviewed_sources(pair: UrlProxyPair) -> UrlProxyPair:
    return replace(
        pair,
        key=replace(
            pair.key,
            reviewed_source=REVIEWED_KEY_SOURCE,
            reviewed_source_detail=pair.key.source_detail_identity(),
            reviewed_occurrence_index=pair.key.occurrence_index_identity(),
        ),
        url=replace(
            pair.url,
            reviewed_source=REVIEWED_URL_SOURCE,
            reviewed_source_detail=pair.url.source_detail_identity(),
            reviewed_occurrence_index=pair.url.occurrence_index_identity(),
        ),
    )


def build_codex_url_proxy_pairs(candidates: list[Candidate]) -> list[UrlProxyPair]:
    provider_candidate = next(
        (
            candidate for candidate in candidates
            if candidate.extra.get("codex_provider_state")
        ),
        None,
    )
    file_keys = [
        candidate for candidate in candidates
        if candidate.role == "api_key" and candidate.source_kind == SourceKind.FILE
    ]
    env_keys = [
        candidate for candidate in candidates
        if candidate.role == "api_key" and candidate.source_kind == SourceKind.PROCESS_ENV
    ]
    env_urls = [
        candidate for candidate in candidates
        if candidate.role == "base_url" and candidate.source_kind == SourceKind.PROCESS_ENV
    ]
    synthesized = [
        candidate for candidate in candidates
        if candidate.role == "synthesized_api_key"
    ]
    if provider_candidate is not None:
        pair = _pair_current_provider(provider_candidate, candidates, file_keys, env_keys, env_urls)
        return [with_reviewed_sources(pair)] if pair is not None else []

    fallback_key = next((key for key in file_keys if key.field == "OPENAI_API_KEY"), None)
    if fallback_key is None:
        fallback_key = next((key for key in env_keys if key.field == "OPENAI_API_KEY"), None)
    if fallback_key is None:
        fallback_key = next((key for key in synthesized if key.field == "OPENAI_API_KEY"), None)
    if fallback_key is None:
        return []

    url_candidate = (
        next((url for url in env_urls if url.field == "OPENAI_BASE_URL"), None)
        or official_url_candidate(CODEX_AUTH_PROVIDER_NAME)
    )
    pair = _make_codex_pair(
        key_candidate=fallback_key,
        url_candidate=url_candidate,
        is_synthesized=fallback_key.source_kind == SourceKind.SYNTHESIZED or url_candidate.source_kind != SourceKind.FILE,
        group=provider_group(CODEX_AUTH_PROVIDER_NAME, url_candidate.source_relpath or ".codex/config.toml"),
    )
    return [with_reviewed_sources(pair)]


def _pair_current_provider(
    provider_candidate: Candidate,
    candidates: list[Candidate],
    file_keys: list[Candidate],
    env_keys: list[Candidate],
    env_urls: list[Candidate],
) -> Optional[UrlProxyPair]:
    provider = str(provider_candidate.extra.get("provider_name", "") or "").strip()
    if not provider:
        return None
    if not provider_candidate.extra.get("provider_exists"):
        return None
    actual_key = (
        next((file_key for file_key in file_keys if file_key.field == provider_candidate.field and file_key.value), None)
        or next((env_key for env_key in env_keys if env_key.field == provider_candidate.field and env_key.value), None)
        or next((file_key for file_key in file_keys if file_key.field == provider_candidate.field), None)
        or next((env_key for env_key in env_keys if env_key.field == provider_candidate.field), None)
        or provider_candidate
    )
    url_candidate = next(
        (
            candidate for candidate in candidates
            if candidate.role == "base_url"
            and str(candidate.extra.get("provider_name", "") or "").strip() == provider
        ),
        None,
    )
    if url_candidate is None:
        if provider != CODEX_AUTH_PROVIDER_NAME:
            return None
        url_candidate = (
            next((url for url in env_urls if url.field == "OPENAI_BASE_URL"), None)
            or official_url_candidate(provider, provider_candidate.source_relpath or ".codex/config.toml")
        )
    return _make_codex_pair(
        key_candidate=actual_key,
        url_candidate=url_candidate,
        is_synthesized=actual_key.source_kind == SourceKind.SYNTHESIZED or url_candidate.source_kind == SourceKind.SYNTHESIZED,
        group=provider_group(provider, url_candidate.source_relpath or provider_candidate.source_relpath or ".codex/config.toml"),
        model=str(provider_candidate.extra.get("model", "") or "").strip(),
        api_format=str(provider_candidate.extra.get("api_format", "") or "").strip(),
    )


__all__ = [
    "CODEX_CONTRACT_ID",
    "CODEX_SERVICE",
    "REVIEWED_KEY_SOURCE",
    "REVIEWED_URL_SOURCE",
    "build_codex_url_proxy_pairs",
    "official_url_candidate",
    "provider_group",
    "with_reviewed_sources",
]
