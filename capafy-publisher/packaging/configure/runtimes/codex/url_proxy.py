from __future__ import annotations

from packaging._shared.codex.home import resolve_codex_home
from packaging.configure.candidate import Candidate
from packaging.configure.contracts import UrlProxyPair
from packaging.configure.runtimes.codex.provider_scan import scan_provider_metadata
from packaging.configure.runtimes.codex.provider_validation import (
    validate_codex_provider_capability,
)
from packaging.configure.runtimes.codex.url_proxy_pairs import build_codex_url_proxy_pairs
from packaging.configure.url_proxy.base import RuntimeContract, ScanContext

_ID = "codex"


class CodexRuntime(RuntimeContract):
    runtime_id = _ID

    def scan(self, ctx: ScanContext) -> list[Candidate]:
        codex_home = resolve_codex_home(home=ctx.user_home)
        return scan_provider_metadata(ctx, codex_home / "config.toml")

    def pair(self, candidates: list[Candidate]) -> list[UrlProxyPair]:
        pairs = build_codex_url_proxy_pairs(candidates)
        for pair in pairs:
            validate_codex_provider_capability(
                api_format=pair.api_format,
                provider_name=pair.provider_name,
                base_url=pair.url.original_value,
            )
        return pairs

__all__ = ["CodexRuntime"]
