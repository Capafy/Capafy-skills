from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Optional, TypeVar

from packaging.configure.contracts import FieldLocation, ReviewedScanBuildInput


@dataclass(frozen=True)
class StripTarget:
    value: str
    placeholder: str
    source_relpath: str = ""
    field: str = ""
    source_detail: str = ""
    occurrence_index: int = 0
    location_fmt: str = ""
    line_number: int = 0
    json_pointer: str = ""
    toml_section: str = ""


StripValue = StripTarget


T = TypeVar("T")


def ordered_unique_strip_values(
    items: Iterable[T],
    extract: Callable[[T], Optional[tuple[str, str]]],
    *,
    sort_ties_by_value: bool = False,
) -> list[StripTarget]:
    targets: list[StripTarget] = []
    seen_values: set[str] = set()
    for item in items:
        spec = extract(item)
        if spec is None:
            continue
        value, placeholder = spec
        if not value or value in seen_values:
            continue
        targets.append(StripTarget(value=value, placeholder=placeholder))
        seen_values.add(value)
    if sort_ties_by_value:
        targets.sort(key=lambda target: (-len(target.value), target.value))
    else:
        targets.sort(key=lambda target: len(target.value), reverse=True)
    return targets


def _item_sources(item: dict) -> list[str]:
    source = str(item.get("source", "") or "").strip()
    return [source] if source else []


def _extend_unique(items: list[str], values: Iterable[str]) -> None:
    for value in values:
        if value not in items:
            items.append(value)


def collect_strip_item_targets(
    strip_items: Iterable[dict],
    *,
    placeholder_candidates_for_item: Callable[[dict], Iterable[str]],
) -> list[dict]:
    targets_by_value: dict[str, dict] = {}
    raw_specs: list[tuple[str, str]] = []
    for item in strip_items:
        if not isinstance(item, dict):
            raise ValueError("strip items must be objects")
        value = str(item.get("value", ""))
        placeholder = str(item.get("placeholder", ""))
        if not value:
            if placeholder:
                continue
            raise ValueError("strip items must include a non-empty value")
        if not placeholder:
            raise ValueError("strip items must include a non-empty placeholder")

        sources = _item_sources(item)
        raw_specs.append((value, placeholder))
        existing = targets_by_value.get(value)
        if existing is None:
            targets_by_value[value] = {
                "value": value,
                "placeholder": placeholder,
                "sources": sources,
                "placeholder_candidates": list(placeholder_candidates_for_item(item)),
                "items": [dict(item)],
            }
            continue
        _extend_unique(existing["sources"], sources)
        _extend_unique(
            existing["placeholder_candidates"],
            placeholder_candidates_for_item(item),
        )
        existing.setdefault("items", []).append(dict(item))
    ordered_values = ordered_unique_strip_values(
        raw_specs,
        lambda item: item,
        sort_ties_by_value=True,
    )
    return [targets_by_value[target.value] for target in ordered_values]


def collect_reviewed_scan_input_strip_targets(reviewed_scan_input: ReviewedScanBuildInput) -> list[StripTarget]:
    raw_targets = [
        *(
            _target_from_plan_field(f)
            for pair in reviewed_scan_input.url_proxy_pairs
            for f in (pair.key, pair.url)
        ),
        *(
            StripTarget(
                value=gv.original_value,
                placeholder=gv.placeholder,
                source_relpath=gv.source_relpath,
                field=gv.field,
                source_detail=gv.location.to_source_detail(gv.field),
                occurrence_index=gv.location.occurrence_index_identity(),
                location_fmt=gv.location.fmt,
                line_number=gv.location.line_number,
                json_pointer=gv.location.json_pointer,
                toml_section=gv.location.toml_section,
            )
            for gv in reviewed_scan_input.generic_values
        ),
        *(
            StripTarget(
                value=ev.process_value,
                placeholder=ev.placeholder,
                field=ev.name,
            )
            for ev in reviewed_scan_input.env_vars
        ),
    ]

    targets_by_identity: dict[tuple[str, str, str, int, str], StripTarget] = {}
    for target in raw_targets:
        if not target.value or not target.placeholder:
            continue
        identity = (
            target.source_relpath,
            target.field,
            target.source_detail,
            target.occurrence_index,
            target.value,
        )
        targets_by_identity.setdefault(identity, target)
    return sorted(
        targets_by_identity.values(),
        key=lambda target: (-len(target.value), target.source_relpath, target.occurrence_index),
    )


def _target_from_plan_field(plan_field) -> StripTarget:
    source_detail = plan_field.source_detail_identity()
    location = _plan_field_location(plan_field, source_detail)
    occurrence_index = plan_field.occurrence_index_identity() if location is not None else 0
    return StripTarget(
        value=plan_field.original_value,
        placeholder=plan_field.placeholder,
        source_relpath=plan_field.source_identity(),
        field=plan_field.field,
        source_detail=source_detail,
        occurrence_index=occurrence_index,
        location_fmt=location.fmt if location is not None else "",
        line_number=location.line_number if location is not None else 0,
        json_pointer=location.json_pointer if location is not None else "",
        toml_section=location.toml_section if location is not None else "",
    )


def _plan_field_location(plan_field, source_detail: str):
    if source_detail:
        return FieldLocation.from_source_detail(source_detail, field=plan_field.field)
    return plan_field.location


__all__ = [
    "StripTarget",
    "StripValue",
    "collect_reviewed_scan_input_strip_targets",
    "collect_strip_item_targets",
    "ordered_unique_strip_values",
]
