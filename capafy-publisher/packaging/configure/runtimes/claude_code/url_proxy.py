from __future__ import annotations

from dataclasses import replace
from packaging._shared.common.home import current_home_from_env
from packaging._shared.llm.api_formats import PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES
from packaging._shared.llm.official_providers import ALL_OFFICIAL_PROVIDER_SPECS_BY_FAMILY
from packaging.configure.candidate import Candidate
from packaging.configure.contracts import SourceKind, UrlProxyPair
from packaging.configure.runtimes.claude_code.auth import (
    CLAUDE_AUTH_TOKEN_ENV_KEY,
    CLAUDE_BASE_URL_ENV_KEY,
)
from packaging.configure.runtimes.claude_code.settings_json import (
    SETTINGS_RELPATH,
    validate_claude_settings_json,
)
from packaging.configure.runtimes.claude_code.url_proxy_candidates import (
    resolve_settings_model,
    resolve_settings_url,
)
from packaging.configure.url_proxy.base import RuntimeContract, ScanContext
from packaging.configure.url_proxy.pair_builder import make_pair

_ID = "claude_code"
_SERVICE = "Anthropic"
_API_FORMAT = PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES
_PROVIDER_NAME = ALL_OFFICIAL_PROVIDER_SPECS_BY_FAMILY["anthropic"].provider_name


class ClaudeCodeRuntime(RuntimeContract):
    runtime_id = _ID

    def scan(self, ctx: ScanContext) -> list[Candidate]:
        user_home = ctx.user_home or current_home_from_env()
        claude_home = user_home / ".claude" if user_home is not None else None
        validate_claude_settings_json(claude_home)
        model = resolve_settings_model(
            claude_home,
            ctx.staging_root,
            ctx.process_env,
        )
        url = resolve_settings_url(claude_home, ctx.process_env)
        key_candidate = Candidate(
            role="synthesized_api_key",
            field=CLAUDE_AUTH_TOKEN_ENV_KEY,
            value="",
            source_kind=SourceKind.SYNTHESIZED,
            source_relpath="",
            extra={"model": model.value},
        )
        url_candidate = Candidate(
            role="base_url",
            field=CLAUDE_BASE_URL_ENV_KEY,
            value=url.value,
            source_kind=(
                SourceKind.FILE
                if url.kind == "settings"
                else SourceKind.PROCESS_ENV
                if url.kind == "process_env"
                else SourceKind.SYNTHESIZED
            ),
            source_relpath=url.source_relpath or SETTINGS_RELPATH,
        )
        return [key_candidate, url_candidate]

    def pair(self, candidates: list[Candidate]) -> list[UrlProxyPair]:
        key_candidate = next(
            (candidate for candidate in candidates if candidate.role == "synthesized_api_key"),
            None,
        )
        url_candidate = next(
            (candidate for candidate in candidates if candidate.role == "base_url"),
            None,
        )
        if key_candidate is None or url_candidate is None:
            return []
        pair = make_pair(
            contract_id=_ID,
            service=_SERVICE,
            key_candidate=key_candidate,
            url_candidate=url_candidate,
            is_synthesized=True,
            group=SETTINGS_RELPATH,
            model=str(key_candidate.extra.get("model", "") or "").strip(),
            api_format=_API_FORMAT,
            provider_name=_PROVIDER_NAME,
        )
        return [
            replace(
                pair,
                key=replace(
                    pair.key,
                    reviewed_source=SETTINGS_RELPATH,
                    reviewed_source_detail="",
                    reviewed_occurrence_index=1,
                ),
                url=replace(
                    pair.url,
                    reviewed_source=SETTINGS_RELPATH,
                    reviewed_source_detail="",
                    reviewed_occurrence_index=1,
                ),
            )
        ]

__all__ = ["ClaudeCodeRuntime"]
