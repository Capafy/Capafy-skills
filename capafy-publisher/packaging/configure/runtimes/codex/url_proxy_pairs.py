from __future__ import annotations

from dataclasses import replace

from packaging._shared.common.constants import OPENAI_OFFICIAL_URL_V1
from packaging._shared.common.url_values import build_config_url_proxy_group
from packaging.configure.candidate import Candidate
from packaging.configure.contracts import FieldLocation, SourceKind, UrlProxyPair
from packaging.configure.runtimes.codex.auth import CODEX_AUTH_PROVIDER_NAME
from packaging.configure.runtimes.codex.url_proxy_candidates import (
    has_non_openai_selected_provider,
    process_env_openai_base_url_candidate,
    top_level_openai_base_url_candidate,
)
from packaging.configure.url_proxy.pair_builder import make_pair

REVIEWED_KEY_SOURCE = ".codex/.env"
REVIEWED_URL_SOURCE = ".codex/config.toml"
CODEX_CONTRACT_ID = "codex"
CODEX_SERVICE = "OpenAI"
OFFICIAL_PROVIDER_NAME = CODEX_AUTH_PROVIDER_NAME


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


def can_synthesize_model_provider_url(key_candidate: Candidate) -> bool:
    return bool(str(key_candidate.field or "").strip())


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
    selected_provider_blocked = has_non_openai_selected_provider(candidates)
    section_keys: dict[str, Candidate] = {}
    section_urls: dict[str, Candidate] = {}
    provider_metadata: dict[str, dict[str, str]] = {}
    for candidate in candidates:
        provider = candidate.extra.get("provider_name", "")
        if not provider:
            continue
        metadata = provider_metadata.setdefault(str(provider), {})
        model = str(candidate.extra.get("model", "") or "").strip()
        api_format = str(candidate.extra.get("api_format", "") or "").strip()
        if model and "model" not in metadata:
            metadata["model"] = model
        if api_format and "api_format" not in metadata:
            metadata["api_format"] = api_format
        if candidate.role == "api_key":
            section_keys.setdefault(provider, candidate)
        elif candidate.role == "base_url":
            section_urls.setdefault(provider, candidate)

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
    synthesized_keys_by_field: dict[str, Candidate] = {}
    for synthesized_key in synthesized:
        if synthesized_key.value and synthesized_key.field not in synthesized_keys_by_field:
            synthesized_keys_by_field[synthesized_key.field] = synthesized_key
    section_key_fields = {section_key.field for section_key in section_keys.values()}

    pairs: list[UrlProxyPair] = []


    for provider, section_key in section_keys.items():
        url_candidate = section_urls.get(provider)
        actual_key = (
            next((file_key for file_key in file_keys if file_key.field == section_key.field and file_key.value), None)
            or next((env_key for env_key in env_keys if env_key.field == section_key.field and env_key.value), None)
            or next((file_key for file_key in file_keys if file_key.field == section_key.field), None)
            or next((env_key for env_key in env_keys if env_key.field == section_key.field), None)
            or synthesized_keys_by_field.get(section_key.field)
            or section_key
        )
        if url_candidate:
            if (
                not str(actual_key.value or "").strip()
                and any(file_key.field not in section_key_fields for file_key in file_keys)
            ):
                continue
            pairs.append(make_pair(
                contract_id=CODEX_CONTRACT_ID,
                service=CODEX_SERVICE,
                key_candidate=actual_key,
                url_candidate=url_candidate,
                is_synthesized=actual_key.source_kind == SourceKind.SYNTHESIZED,
                group=provider_group(
                    provider,
                    url_candidate.source_relpath or section_key.source_relpath or ".codex/config.toml",
                ),
                model=provider_metadata.get(str(provider), {}).get("model", ""),
                api_format=provider_metadata.get(str(provider), {}).get("api_format", ""),
            ))
        elif can_synthesize_model_provider_url(actual_key):
            source = section_key.source_relpath or ".codex/config.toml"
            pairs.append(make_pair(
                contract_id=CODEX_CONTRACT_ID,
                service=CODEX_SERVICE,
                key_candidate=actual_key,
                url_candidate=official_url_candidate(provider, source),
                is_synthesized=actual_key.source_kind == SourceKind.SYNTHESIZED,
                group=provider_group(provider, source),
                model=provider_metadata.get(str(provider), {}).get("model", ""),
                api_format=provider_metadata.get(str(provider), {}).get("api_format", ""),
            ))


    if file_keys:
        for file_key in file_keys:
            if file_key.field in section_key_fields:
                continue
            if file_key.field != "OPENAI_API_KEY":
                continue
            provider = OFFICIAL_PROVIDER_NAME
            top_level_url = top_level_openai_base_url_candidate(candidates)
            if top_level_url:
                provider = str(top_level_url.extra.get("provider_name", "") or provider).strip() or provider
                pairs.append(make_pair(
                    contract_id=CODEX_CONTRACT_ID,
                    service=CODEX_SERVICE,
                    key_candidate=file_key,
                    url_candidate=top_level_url,
                    group=provider_group(provider, top_level_url.source_relpath or ".codex/config.toml"),
                ))
                continue





            process_env_url = process_env_openai_base_url_candidate(candidates)
            if process_env_url:
                pairs.append(make_pair(
                    contract_id=CODEX_CONTRACT_ID,
                    service=CODEX_SERVICE,
                    key_candidate=file_key,
                    url_candidate=process_env_url,
                    is_synthesized=True,
                    group=provider_group(provider, process_env_url.source_relpath or ".codex/config.toml"),
                ))
                continue
            pairs.append(make_pair(
                contract_id=CODEX_CONTRACT_ID,
                service=CODEX_SERVICE,
                key_candidate=file_key,
                url_candidate=official_url_candidate(provider),
                is_synthesized=True,
                group=provider_group(provider),
            ))
        if pairs:
            return [with_reviewed_sources(pair) for pair in pairs]


    if not pairs and env_keys:
        for env_key in env_keys:
            if env_key.field in section_key_fields or env_key.extra.get("env_key_reference"):
                continue
            if env_key.field != "OPENAI_API_KEY":
                continue
            top_level_url = top_level_openai_base_url_candidate(candidates)
            if top_level_url:
                provider = (
                    str(top_level_url.extra.get("provider_name", "") or OFFICIAL_PROVIDER_NAME).strip()
                    or OFFICIAL_PROVIDER_NAME
                )
                pairs.append(make_pair(
                    contract_id=CODEX_CONTRACT_ID,
                    service=CODEX_SERVICE,
                    key_candidate=env_key,
                    url_candidate=top_level_url,
                    is_synthesized=True,
                    group=provider_group(provider, top_level_url.source_relpath or ".codex/config.toml"),
                ))
                continue
            if selected_provider_blocked:
                continue
            process_env_url = next(
                (url for url in env_urls if url.field == "OPENAI_BASE_URL"),
                env_urls[0] if env_urls else None,
            )
            if process_env_url:
                pairs.append(make_pair(
                    contract_id=CODEX_CONTRACT_ID,
                    service=CODEX_SERVICE,
                    key_candidate=env_key,
                    url_candidate=process_env_url,
                    is_synthesized=True,
                    group=provider_group(OFFICIAL_PROVIDER_NAME, process_env_url.source_relpath or ".codex/config.toml"),
                ))
            else:
                pairs.append(make_pair(
                    contract_id=CODEX_CONTRACT_ID,
                    service=CODEX_SERVICE,
                    key_candidate=env_key,
                    url_candidate=official_url_candidate(OFFICIAL_PROVIDER_NAME),
                    is_synthesized=True,
                    group=provider_group(OFFICIAL_PROVIDER_NAME),
                ))


    if not pairs and synthesized and not section_keys:
        for synthesized_key in synthesized:
            if synthesized_key.field != "OPENAI_API_KEY":
                continue
            top_level_url = top_level_openai_base_url_candidate(candidates)
            if top_level_url:
                provider = (
                    str(top_level_url.extra.get("provider_name", "") or OFFICIAL_PROVIDER_NAME).strip()
                    or OFFICIAL_PROVIDER_NAME
                )
                pairs.append(make_pair(
                    contract_id=CODEX_CONTRACT_ID,
                    service=CODEX_SERVICE,
                    key_candidate=synthesized_key,
                    url_candidate=top_level_url,
                    is_synthesized=True,
                    group=provider_group(provider, top_level_url.source_relpath or ".codex/config.toml"),
                ))
                continue
            if selected_provider_blocked:
                continue
            process_env_url = process_env_openai_base_url_candidate(candidates)
            if process_env_url:
                pairs.append(make_pair(
                    contract_id=CODEX_CONTRACT_ID,
                    service=CODEX_SERVICE,
                    key_candidate=synthesized_key,
                    url_candidate=process_env_url,
                    is_synthesized=True,
                    group=provider_group(OFFICIAL_PROVIDER_NAME, process_env_url.source_relpath or ".codex/config.toml"),
                ))
                continue
            pairs.append(make_pair(
                contract_id=CODEX_CONTRACT_ID,
                service=CODEX_SERVICE,
                key_candidate=synthesized_key,
                url_candidate=official_url_candidate(OFFICIAL_PROVIDER_NAME),
                is_synthesized=True,
                group=provider_group(OFFICIAL_PROVIDER_NAME),
            ))

    return [with_reviewed_sources(pair) for pair in pairs]


__all__ = [
    "CODEX_CONTRACT_ID",
    "CODEX_SERVICE",
    "OFFICIAL_PROVIDER_NAME",
    "REVIEWED_KEY_SOURCE",
    "REVIEWED_URL_SOURCE",
    "build_codex_url_proxy_pairs",
    "can_synthesize_model_provider_url",
    "official_url_candidate",
    "provider_group",
    "with_reviewed_sources",
]
