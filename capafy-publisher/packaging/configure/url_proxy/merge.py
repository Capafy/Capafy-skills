from __future__ import annotations

from packaging.configure.contracts import SourceKind, UrlProxyPair


def _pair_identity(pair: UrlProxyPair) -> tuple[str, str, int, str, str, int]:
    return (
        str(getattr(pair.key, "source_relpath", "") or "").strip(),
        str(getattr(pair.key, "original_value", "") or "").strip(),
        pair.key.occurrence_index_identity(),
        str(getattr(pair.url, "source_relpath", "") or "").strip(),
        str(getattr(pair.url, "original_value", "") or "").strip(),
        pair.url.occurrence_index_identity(),
    )


def _semantic_pair_identity(pair: UrlProxyPair) -> tuple[str, str, str]:
    return (
        str(getattr(pair, "group", "") or "").strip(),
        str(getattr(pair.key, "original_value", "") or "").strip(),
        str(getattr(pair.url, "original_value", "") or "").strip(),
    )


def dedupe_cross_source_pairs(
    runtime_pairs: list[UrlProxyPair],
    structured_pairs: list[UrlProxyPair],
) -> tuple[list[UrlProxyPair], int]:
    runtime_semantic_identities = {
        identity
        for identity in (_semantic_pair_identity(pair) for pair in runtime_pairs)
        if all(identity)
    }
    runtime_key_identities = {
        (
            str(getattr(pair.key, "source_relpath", "") or "").strip(),
            str(getattr(pair.key, "original_value", "") or "").strip(),
        )
        for pair in runtime_pairs
        if str(getattr(pair.key, "source_relpath", "") or "").strip()
        and str(getattr(pair.key, "original_value", "") or "").strip()
    }
    all_pairs: list[UrlProxyPair] = []
    seen_identities: set[tuple[str, str, int, str, str, int]] = set()
    duplicate_count = 0
    for pair_source, pairs in (("runtime", runtime_pairs), ("structured", structured_pairs)):
        for pair in pairs:
            identity = _pair_identity(pair)
            semantic_identity = _semantic_pair_identity(pair)

            if not (identity[1] or identity[4]):
                all_pairs.append(pair)
                continue
            if identity in seen_identities:
                duplicate_count += 1
                continue


            if pair_source == "structured" and (identity[0], identity[1]) in runtime_key_identities:
                duplicate_count += 1
                continue
            if (
                pair_source == "structured"
                and all(semantic_identity)
                and semantic_identity in runtime_semantic_identities
            ):
                duplicate_count += 1
                continue
            seen_identities.add(identity)
            all_pairs.append(pair)
    return all_pairs, duplicate_count


def dedupe_fallback_generic_entries(
    entries: list[dict],
    runtime_pairs: list[UrlProxyPair],
) -> list[dict]:
    runtime_owned_keys: set[tuple[str, str, int]] = set()
    for pair in runtime_pairs:
        for plan_field in (pair.key, pair.url):
            relpath = str(getattr(plan_field, "source_relpath", "") or "").strip()
            value = str(getattr(plan_field, "original_value", "") or "").strip()
            occ = plan_field.occurrence_index_identity()
            if relpath or value:
                runtime_owned_keys.add((relpath, value, occ))

    deduped: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_source = str(entry.get("source", "") or "").strip()
        entry_value = str(entry.get("value", "") or "").strip()
        try:
            entry_occ = int(entry.get("occurrence_index", 1))
        except (TypeError, ValueError):
            entry_occ = 1
        if entry_occ <= 0:
            entry_occ = 1
        if (entry_source, entry_value, entry_occ) in runtime_owned_keys:
            continue
        deduped.append(entry)
    return deduped


def collect_claimed_process_env_names(pairs: list[UrlProxyPair]) -> frozenset[str]:
    claimed: set[str] = set()
    for pair in pairs:
        for plan_field in (pair.key, pair.url):
            field_name = str(getattr(plan_field, "field", "") or "").strip()
            if not field_name:
                continue
            if getattr(plan_field, "source_kind", None) == SourceKind.PROCESS_ENV:
                claimed.add(field_name)
    return frozenset(claimed)


__all__ = [
    "collect_claimed_process_env_names",
    "dedupe_cross_source_pairs",
    "dedupe_fallback_generic_entries",
]
