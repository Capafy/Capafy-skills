from __future__ import annotations

from packaging.configure.contracts import GenericValue, ReviewedScanBuildInput, SourceKind, UrlProxyPair


LocationIdentity = tuple[str, str, str, int, str]


def _plan_field_identity(plan_field) -> LocationIdentity:
    return (
        str(plan_field.source_identity() or "").strip(),
        str(getattr(plan_field, "field", "") or "").strip(),
        str(plan_field.source_detail_identity() or "").strip(),
        plan_field.occurrence_index_identity(),
        str(getattr(plan_field, "original_value", "") or "").strip(),
    )


def _generic_value_identity(generic_value: GenericValue) -> LocationIdentity:
    return (
        str(generic_value.source_relpath or "").strip(),
        str(generic_value.field or "").strip(),
        generic_value.location.to_source_detail(generic_value.field),
        generic_value.location.occurrence_index_identity(),
        str(generic_value.original_value or "").strip(),
    )


def _generic_entry_identity(entry: dict) -> LocationIdentity:
    try:
        occurrence_index = int(entry.get("occurrence_index", 1))
    except (TypeError, ValueError):
        occurrence_index = 1
    if occurrence_index <= 0:
        occurrence_index = 1
    return (
        str(entry.get("source", "") or "").strip(),
        str(entry.get("field", "") or "").strip(),
        str(entry.get("source_detail", "") or "").strip(),
        occurrence_index,
        str(entry.get("value", "") or "").strip(),
    )


def _claimed_location_identities(pairs: list[UrlProxyPair]) -> set[LocationIdentity]:
    identities: set[LocationIdentity] = set()
    for pair in pairs:
        for plan_field in (pair.key, pair.url):
            identity = _plan_field_identity(plan_field)
            if any(identity):
                identities.add(identity)
    return identities


def _pair_identity(pair: UrlProxyPair) -> tuple[LocationIdentity, LocationIdentity]:
    return (
        _plan_field_identity(pair.key),
        _plan_field_identity(pair.url),
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
    runtime_key_identities: set[LocationIdentity] = set()
    for pair in runtime_pairs:
        key_identity = _plan_field_identity(pair.key)
        if key_identity[0] and key_identity[4]:
            runtime_key_identities.add(key_identity)
    all_pairs: list[UrlProxyPair] = []
    seen_identities: set[tuple[LocationIdentity, LocationIdentity]] = set()
    duplicate_count = 0
    for pair_source, pairs in (("runtime", runtime_pairs), ("structured", structured_pairs)):
        for pair in pairs:
            identity = _pair_identity(pair)
            semantic_identity = _semantic_pair_identity(pair)

            key_identity, url_identity = identity
            if not (key_identity[4] or url_identity[4]):
                all_pairs.append(pair)
                continue
            if identity in seen_identities:
                duplicate_count += 1
                continue


            if pair_source == "structured" and key_identity in runtime_key_identities:
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
    claimed_identities = _claimed_location_identities(runtime_pairs)
    deduped: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if _generic_entry_identity(entry) in claimed_identities:
            continue
        deduped.append(entry)
    return deduped


def filter_url_proxy_claimed_reviewed_input(reviewed_input: ReviewedScanBuildInput) -> ReviewedScanBuildInput:
    claimed_identities = _claimed_location_identities(list(reviewed_input.url_proxy_pairs))
    claimed_env_names = collect_claimed_process_env_names(list(reviewed_input.url_proxy_pairs))
    generic_values = tuple(
        generic_value
        for generic_value in reviewed_input.generic_values
        if _generic_value_identity(generic_value) not in claimed_identities
    )
    env_vars = tuple(
        env_var
        for env_var in reviewed_input.env_vars
        if str(env_var.name or "").strip() not in claimed_env_names
    )
    if generic_values == reviewed_input.generic_values and env_vars == reviewed_input.env_vars:
        return reviewed_input
    return ReviewedScanBuildInput(
        url_proxy_pairs=reviewed_input.url_proxy_pairs,
        generic_values=generic_values,
        env_vars=env_vars,
        excludes=reviewed_input.excludes,
    )


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
    "filter_url_proxy_claimed_reviewed_input",
]
