from __future__ import annotations

from packaging.configure.contracts import GenericValue, ReviewedScanBuildInput, UrlProxyPair
from packaging.configure.url_proxy.base import RuntimeContract


LocationIdentity = tuple[str, str, str, int, str]
SemanticFieldIdentity = tuple[str, str, str]


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


def _runtime_semantic_field_identity(
    runtime: RuntimeContract,
    field_obj,
) -> SemanticFieldIdentity:
    identity = runtime.semantic_field_identity(field_obj)
    normalized = tuple(str(part or "").strip() for part in identity)
    if len(normalized) == 3 and all(normalized):
        return normalized
    return ("", "", "")


def _claimed_location_identities(pairs: list[UrlProxyPair]) -> set[LocationIdentity]:
    identities: set[LocationIdentity] = set()
    for pair in pairs:
        for plan_field in (pair.key, pair.url):
            identity = _plan_field_identity(plan_field)
            if any(identity):
                identities.add(identity)
    return identities


def _claimed_semantic_field_identities(
    pairs: list[UrlProxyPair],
    runtime: RuntimeContract,
) -> set[SemanticFieldIdentity]:
    identities: set[SemanticFieldIdentity] = set()
    for pair in pairs:
        for plan_field in (pair.key, pair.url):
            identity = _runtime_semantic_field_identity(runtime, plan_field)
            if all(identity):
                identities.add(identity)
    return identities


def filter_url_proxy_claimed_reviewed_input(
    reviewed_input: ReviewedScanBuildInput,
    *,
    runtime: RuntimeContract,
) -> ReviewedScanBuildInput:
    claimed_identities = _claimed_location_identities(list(reviewed_input.url_proxy_pairs))
    claimed_semantic_fields = _claimed_semantic_field_identities(
        list(reviewed_input.url_proxy_pairs),
        runtime,
    )
    generic_values = tuple(
        generic_value
        for generic_value in reviewed_input.generic_values
        if _generic_value_identity(generic_value) not in claimed_identities
        and _runtime_semantic_field_identity(runtime, generic_value)
        not in claimed_semantic_fields
    )
    if generic_values == reviewed_input.generic_values:
        return reviewed_input
    return ReviewedScanBuildInput(
        url_proxy_pairs=reviewed_input.url_proxy_pairs,
        generic_values=generic_values,
    )


__all__ = ["filter_url_proxy_claimed_reviewed_input"]
