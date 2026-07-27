from __future__ import annotations

from dataclasses import replace

from packaging._shared.common.url_values import build_config_url_proxy_group
from packaging.configure.candidate import Candidate
from packaging.configure.contracts import UrlProxyPair
from packaging.configure.runtimes.codex.config_state import CONFIG_RELPATH, DEFAULT_CODEX_API_FORMAT
from packaging.configure.url_proxy.pair_builder import make_pair

REVIEWED_KEY_SOURCE = ".codex/.env"
REVIEWED_URL_SOURCE = CONFIG_RELPATH
CODEX_CONTRACT_ID = "codex"
CODEX_SERVICE = "OpenAI"


def provider_group(provider_name: str) -> str:
    return build_config_url_proxy_group(CONFIG_RELPATH, f"model_providers.{provider_name}")


def with_reviewed_sources(pair: UrlProxyPair) -> UrlProxyPair:
    return replace(
        pair,
        key=replace(
            pair.key,
            reviewed_source=REVIEWED_KEY_SOURCE,
            reviewed_source_detail="",
            reviewed_occurrence_index=1,
        ),
        url=replace(
            pair.url,
            reviewed_source=REVIEWED_URL_SOURCE,
            reviewed_source_detail=pair.url.source_detail_identity(),
            reviewed_occurrence_index=pair.url.occurrence_index_identity(),
        ),
    )


def build_codex_url_proxy_pairs(candidates: list[Candidate]) -> list[UrlProxyPair]:
    key_candidate = next(
        (
            candidate
            for candidate in candidates
            if candidate.role == "synthesized_api_key"
            and candidate.extra.get("codex_provider_state")
        ),
        None,
    )
    if key_candidate is None:
        return []
    provider_name = str(key_candidate.extra.get("provider_name", "") or "").strip()
    url_candidate = next(
        (
            candidate
            for candidate in candidates
            if candidate.role == "base_url"
            and str(candidate.extra.get("provider_name", "") or "").strip() == provider_name
        ),
        None,
    )
    if not provider_name or url_candidate is None:
        return []
    pair = make_pair(
        contract_id=CODEX_CONTRACT_ID,
        service=CODEX_SERVICE,
        key_candidate=key_candidate,
        url_candidate=url_candidate,
        is_synthesized=True,
        group=provider_group(provider_name),
        model=str(key_candidate.extra.get("model", "") or "").strip(),
        api_format=str(key_candidate.extra.get("api_format", "") or "").strip()
        or DEFAULT_CODEX_API_FORMAT,
        provider_name=provider_name,
    )
    return [with_reviewed_sources(pair)]


__all__ = [
    "CODEX_CONTRACT_ID",
    "CODEX_SERVICE",
    "REVIEWED_KEY_SOURCE",
    "REVIEWED_URL_SOURCE",
    "build_codex_url_proxy_pairs",
    "provider_group",
    "with_reviewed_sources",
]
