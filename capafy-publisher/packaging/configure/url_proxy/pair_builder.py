from __future__ import annotations

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


def _candidate_extra_text(candidate: Candidate, key: str) -> str:
    return str(candidate.extra.get(key, "") or "").strip()


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
) -> UrlProxyPair:
    source_for_group = key_candidate.source_relpath or url_candidate.source_relpath or ""
    resolved_group = group or source_for_group or f"<{contract_id}:{key_candidate.field}>"
    resolved_model = (
        model
        or _candidate_extra_text(key_candidate, "model")
        or _candidate_extra_text(url_candidate, "model")
    )
    resolved_api_format = (
        api_format
        or _candidate_extra_text(key_candidate, "api_format")
        or _candidate_extra_text(url_candidate, "api_format")
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
    )


__all__ = [
    "make_pair",
]
