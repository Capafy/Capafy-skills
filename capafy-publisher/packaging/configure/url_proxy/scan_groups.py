from __future__ import annotations

from packaging.configure.contracts import UrlProxyPair
from packaging.configure.url_proxy.entry_converters import url_proxy_entry_to_pair
from packaging.configure.url_proxy.group_hints import UrlProxyPairingHints, apply_url_proxy_group_hints
from packaging.configure.url_proxy.pairing import pair_url_proxy_entries
from packaging.configure.url_proxy.predicates import is_url_proxy_candidate


def build_url_proxy_scan_groups_from_candidates(
    candidates: list[dict],
    hints: UrlProxyPairingHints,
) -> dict[str, list[dict]]:
    from packaging.configure.scan.entries import build_scan_entries, build_scan_groups

    apply_url_proxy_group_hints(candidates)


    grouped_candidates = [c for c in candidates if is_url_proxy_candidate(c)]
    entries = build_scan_entries(
        grouped_candidates,
        hints.env_url_hints,
        hints.service_url_hints,
        hints.value_url_hints,
    )
    url_proxy, generic = pair_url_proxy_entries(entries)
    return build_scan_groups(url_proxy, generic)


def build_url_proxy_pairs_from_candidates(
    candidates: list[dict],
    hints: UrlProxyPairingHints,
    *,
    default_contract_id: str,
) -> tuple[list[UrlProxyPair], list[dict]]:
    scan_groups = build_url_proxy_scan_groups_from_candidates(candidates, hints)

    pairs: list[UrlProxyPair] = []
    for entry in scan_groups.get("url_proxy", []):
        if not isinstance(entry, dict):
            continue
        pair = url_proxy_entry_to_pair(entry, default_contract_id=default_contract_id)
        if pair is not None:
            pairs.append(pair)

    fallback_generic = [
        entry for entry in scan_groups.get("generic", []) if isinstance(entry, dict)
    ]
    return pairs, fallback_generic


__all__ = [
    "build_url_proxy_pairs_from_candidates",
    "build_url_proxy_scan_groups_from_candidates",
]
