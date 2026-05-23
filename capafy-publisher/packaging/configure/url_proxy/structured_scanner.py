from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from packaging.configure.contracts import UrlProxyPair


@dataclass(frozen=True)
class StructuredUrlProxyScanResult:

    pairs: list[UrlProxyPair]
    fallback_generic_entries: list[dict]
    claimed_field_names: frozenset[str]


def run_structured_url_proxy_scan(
    staging_root: Path,
    *,
    target_name: str,
    platform_agent_type: str = "run_online",
    default_contract_id: str = "STRUCTURED",
) -> StructuredUrlProxyScanResult:
    from packaging.configure.contracts import SourceKind
    from packaging.configure.scan.staging_scan import collect_staging_scan_candidates
    from packaging.configure.url_proxy.group_hints import UrlProxyPairingHints
    from packaging.configure.url_proxy.scan_groups import (
        build_url_proxy_pairs_from_candidates,
    )

    (
        candidates,
        _excludes,
        env_url_hints,
        service_url_hints,
        value_url_hints,
        _referenced_env_names,
    ) = collect_staging_scan_candidates(
        staging_root,
        target_name=target_name,
        platform_agent_type=platform_agent_type,
    )

    pairs, fallback_generic = build_url_proxy_pairs_from_candidates(
        candidates,
        UrlProxyPairingHints(
            env_url_hints=env_url_hints,
            service_url_hints=service_url_hints,
            value_url_hints=value_url_hints,
        ),
        default_contract_id=default_contract_id,
    )

    claimed: set[str] = set()
    for pair in pairs:
        for plan_field in (pair.key, pair.url):
            field = str(getattr(plan_field, "field", "") or "").strip()
            if not field:
                continue
            if getattr(plan_field, "source_kind", None) == SourceKind.PROCESS_ENV:
                claimed.add(field)

    return StructuredUrlProxyScanResult(
        pairs=pairs,
        fallback_generic_entries=fallback_generic,
        claimed_field_names=frozenset(claimed),
    )


def rewrite_structured_pairs(staging_root: Path, pairs: list[UrlProxyPair]) -> None:
    from packaging.configure.url_proxy.rewriter import apply_url_proxy_to_staging

    if pairs:
        apply_url_proxy_to_staging(staging_root, pairs)


__all__ = [
    "StructuredUrlProxyScanResult",
    "run_structured_url_proxy_scan",
    "rewrite_structured_pairs",
]
