from __future__ import annotations

from dataclasses import replace

from packaging.configure.contracts import FieldLocation, GenericValue
from packaging.configure.scan.entry_finalize import finalize_entry, entry_field_aliases
from packaging.configure.sensitive.literals import looks_like_platform_managed_placeholder_value
from packaging.configure.use_text import use_for_generic_value


def filter_generic_values(
    raw_generic_items: list[dict],
) -> list[GenericValue]:
    result: list[GenericValue] = []
    for item in raw_generic_items:
        if not isinstance(item, dict):
            continue
        value = str(item.get("value", "")).strip()
        if not value or looks_like_platform_managed_placeholder_value(value):
            continue
        source = str(item.get("source", "") or "").strip()
        if not source:
            continue
        field = str(item.get("field", "")).strip()
        source_detail = str(item.get("source_detail", "") or "").strip()
        location = FieldLocation.from_source_detail(source_detail, field=field) if source_detail else FieldLocation(fmt="json")
        occurrence_index = _positive_int(item.get("occurrence_index"))
        if occurrence_index > 0:
            location = replace(location, occurrence_index=occurrence_index)
        result.append(GenericValue(
            field=field,
            source_relpath=source,
            location=location,
            original_value=value,
            placeholder=str(item.get("placeholder", "")).strip(),
            value_type=str(item.get("value_type", "")).strip(),
        ))
    return result


def _positive_int(value: object) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return 0
    return result if result > 0 else 0


def build_generic_from_entry(entry: dict) -> dict | None:
    source = str(entry.get("source", "") or "").strip()
    if not source:
        return None
    final = finalize_entry(entry)
    role = entry.get("role", "config_value")

    if role == "key":
        vt = "api_key"
    else:
        vt = final.get("value_type", "value")


    field_aliases = [
        alias
        for alias in entry_field_aliases(entry)
        if alias != str(final.get("field", "")).strip()
    ]
    result: dict = {
        "value": final["value"],
        "placeholder": final["placeholder"],
        "field": final.get("field", ""),
        "source": source,
        "source_detail": final.get("source_detail", ""),
        "occurrence_index": final.get("occurrence_index", 1),
        "url": final.get("url", ""),
        "use": use_for_generic_value(
            str(final.get("field", "")),
            str(vt),
            service=str(final.get("service", "")),
            url=str(final.get("url", "")),
        ),
    }
    if field_aliases:
        result["field_aliases"] = field_aliases

    if role != "key":
        result["value_type"] = vt
    return result


__all__ = [
    "build_generic_from_entry",
    "filter_generic_values",
]
