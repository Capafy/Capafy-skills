from __future__ import annotations

from collections.abc import Iterable
from typing import Optional

from packaging.configure.candidate import Candidate
from packaging.configure.contracts import (
    PlanField,
    SourceKind,
    UrlProxyPair,
)
from packaging.configure.sensitive.placeholders import build_placeholder


def _reviewed_source_detail(candidate: Candidate) -> str:
    location = candidate.location
    if location is None:
        return ""
    return location.to_source_detail(candidate.field)


def _reviewed_occurrence_index(candidate: Candidate) -> int:
    location = candidate.location
    if location is None:
        return 1
    return location.occurrence_index_identity()


def usable_provider_key_candidates(candidates: list[Candidate]) -> list[Candidate]:
    return [
        candidate
        for candidate in candidates
        if str(candidate.value or "").strip()
        or bool(candidate.extra.get("placeholder_provider"))
        or candidate.source_kind == SourceKind.SYNTHESIZED
    ]


def first_candidate_extra_value(candidates: Iterable[Optional[Candidate]], field: str) -> str:
    for candidate in candidates:
        if candidate is None:
            continue
        value = str(candidate.extra.get(field, "") or "").strip()
        if value:
            return value
    return ""


def make_pair(
    *,
    contract_id: str,
    service: str,
    key_candidate: Candidate,
    url_candidate: Candidate,
    is_synthesized: bool = False,
    group: str = "",
    model: str = "",
    api_format: str = "",
    provider_name: str = "",
) -> UrlProxyPair:
    source_for_group = key_candidate.source_relpath or url_candidate.source_relpath or ""
    resolved_group = group or source_for_group or f"<{contract_id}:{key_candidate.field}>"
    resolved_model = (
        model
        or str(key_candidate.extra.get("model", "") or "").strip()
        or str(url_candidate.extra.get("model", "") or "").strip()
    )
    resolved_api_format = (
        api_format
        or str(key_candidate.extra.get("api_format", "") or "").strip()
        or str(url_candidate.extra.get("api_format", "") or "").strip()
    )
    resolved_provider_name = (
        provider_name
        or str(key_candidate.extra.get("provider_name", "") or "").strip()
        or str(url_candidate.extra.get("provider_name", "") or "").strip()
    )
    key_placeholder_source = key_candidate.source_relpath or (
        "" if url_candidate.source_kind == SourceKind.SYNTHESIZED else source_for_group
    )
    key_placeholder_locator = "" if url_candidate.source_kind == SourceKind.SYNTHESIZED else url_candidate.value or ""

    key_ph = build_placeholder(
        service,
        key_placeholder_source,
        field=key_candidate.field,
        locator=key_placeholder_locator,
    )
    url_ph = build_placeholder(
        service,
        url_candidate.source_relpath or source_for_group,
        field=url_candidate.field,
        locator=url_candidate.value or "",
        value_type="url",
    )

    return UrlProxyPair(
        contract_id=contract_id,
        service=service,
        group=resolved_group,
        key=PlanField(
            field=key_candidate.field, service=service,
            source_kind=key_candidate.source_kind,
            source_relpath=key_candidate.source_relpath,
            location=key_candidate.location,
            original_value=key_candidate.value,
            placeholder=key_ph,
            reviewed_source_detail=_reviewed_source_detail(key_candidate),
            reviewed_occurrence_index=_reviewed_occurrence_index(key_candidate),
        ),
        url=PlanField(
            field=url_candidate.field, service=service,
            source_kind=url_candidate.source_kind,
            source_relpath=url_candidate.source_relpath,
            location=url_candidate.location,
            original_value=url_candidate.value,
            placeholder=url_ph,
            reviewed_source_detail=_reviewed_source_detail(url_candidate),
            reviewed_occurrence_index=_reviewed_occurrence_index(url_candidate),
        ),
        is_synthesized=is_synthesized,
        model=resolved_model,
        api_format=resolved_api_format,
        provider_name=resolved_provider_name,
    )


__all__ = [
    "first_candidate_extra_value",
    "make_pair",
    "usable_provider_key_candidates",
]
