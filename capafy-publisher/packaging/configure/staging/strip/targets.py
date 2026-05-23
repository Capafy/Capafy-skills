from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TypeVar

from packaging.configure.contracts import ReviewedScanBuildInput


@dataclass(frozen=True)
class StripTarget:
    value: str
    placeholder: str


StripValue = StripTarget


T = TypeVar("T")


def ordered_unique_strip_values(
    items: Iterable[T],
    extract: Callable[[T], tuple[str, str] | None],
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
        *((f.original_value, f.placeholder) for pair in reviewed_scan_input.url_proxy_pairs for f in (pair.key, pair.url)),
        *((gv.original_value, gv.placeholder) for gv in reviewed_scan_input.generic_values),
        *((ev.process_value, ev.placeholder) for ev in reviewed_scan_input.env_vars),
    ]
    return [
        StripTarget(value=target.value, placeholder=target.placeholder)
        for target in ordered_unique_strip_values(raw_targets, lambda item: item)
    ]


__all__ = [
    "StripTarget",
    "StripValue",
    "collect_reviewed_scan_input_strip_targets",
    "collect_strip_item_targets",
    "ordered_unique_strip_values",
]
