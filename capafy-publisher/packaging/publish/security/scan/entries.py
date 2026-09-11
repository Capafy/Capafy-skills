from __future__ import annotations

from dataclasses import replace
from typing import Optional

from packaging.runtime.contracts import FieldLocation, GenericValue, build_placeholder
from packaging.common.text_parse import looks_like_platform_managed_placeholder_value
from packaging.publish.security.sensitive.placeholders import split_source


def use_for_generic_value(
    field: str,
    value_type: str,
    *,
    service: str = "",
    url: str = "",
) -> str:
    label = str(field or "").strip() or str(service or "").strip()
    normalized_type = str(value_type or "").strip().lower()
    normalized_field = str(field or "").strip().lower()
    if normalized_type == "url" or str(url or "").strip() or "url" in normalized_field or "webhook" in normalized_field:
        return f"Service endpoint for {label}" if label else "Service endpoint"
    if normalized_type == "api_key" or any(
        marker in normalized_field
        for marker in ("api_key", "apikey", "access_key", "token", "secret", "password")
    ):
        return f"API key for {label}" if label else "API key"
    return f"Runtime value for {label}" if label else "Runtime value"


def entry_field_aliases(entry: dict) -> list[str]:
    aliases = entry.get("_field_aliases", [])
    if not isinstance(aliases, list):
        aliases = []
    field = str(entry.get("field", "")).strip()
    result: list[str] = []
    for alias in [field, *[str(item) for item in aliases if item]]:
        normalized = alias.strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _placeholder_source(entry: dict) -> str:
    source = str(entry.get("_source_seed") or str(entry.get("source", "")).strip())
    detail = str(entry.get("source_detail", "") or "").strip()
    occurrence = str(entry.get("occurrence_index", "") or "").strip()
    return "\n".join((source, detail, occurrence))


def _placeholder_field(entry: dict) -> str:
    field = str(entry.get("field", "")).strip()
    occurrence = str(
        entry.get("_placeholder_field", "") or entry.get("occurrence_id", "")
    ).strip()
    if not occurrence:
        return field
    return f"{field}#{occurrence}" if field else occurrence


def finalize_entry(entry: dict) -> dict:
    final = dict(entry)
    final["placeholder"] = build_placeholder(
        final["service"],
        _placeholder_source(final),
        field=_placeholder_field(final),
        locator=final["url"],
        value_type=str(final.get("value_type", "")),
    )
    final.pop("_source_seed", None)
    final.pop("_placeholder_field", None)
    return final


def resolve_candidate_url(
    candidate: dict,
    env_url_hints: dict[str, str],
) -> str:
    default_url = candidate["default_url"]
    url = candidate["local_url"]
    env_name = candidate["env_name"]
    if env_name and env_name in env_url_hints:
        return env_url_hints[env_name]
    return url or default_url


def _candidate_role(candidate: dict) -> str:
    if candidate.get("entry_type") == "api_key":
        return "key"
    value_type = candidate.get("value_type") or "value"
    if value_type == "url":
        return "url"
    return "config_value"


def _occurrence_identity(entry: dict) -> tuple[str, str, str]:
    return (
        str(entry.get("source", "") or "").strip(),
        str(entry.get("field", "") or "").strip(),
        str(entry.get("value_type", "") or entry.get("role", "") or "").strip(),
    )


def _assign_scan_entry_occurrence_indexes(entries: list[dict]) -> None:
    counters: dict[tuple[str, str, str], int] = {}
    for entry in entries:
        key = _occurrence_identity(entry)
        counters[key] = counters.get(key, 0) + 1
        entry["occurrence_index"] = counters[key]


def build_scan_entries(
    candidates: list[dict],
    env_url_hints: dict[str, str],
) -> list[dict]:
    entries: list[dict] = []

    for candidate in candidates:
        value = candidate["value"]

        resolved_url = resolve_candidate_url(candidate, env_url_hints)

        source, source_detail = split_source(str(candidate["source"]))
        candidate_source_detail = str(candidate.get("source_detail", "") or "").strip()
        if candidate_source_detail:
            source_detail = candidate_source_detail
        source_seed = source.strip()
        source_path = source_seed.split("#", 1)[0].strip()
        role = _candidate_role(candidate)

        entry: dict = {
            "value": value,
            "role": role,
            "service": candidate["service"],
            "url": resolved_url,
            "source": source_path,
            "_source_seed": source_seed,
        }

        if role != "key":
            entry["value_type"] = candidate.get("value_type") or "value"
        if source_detail:
            entry["source_detail"] = source_detail
        if candidate.get("field"):
            entry["field"] = candidate["field"]

        entries.append(entry)

    _assign_scan_entry_occurrence_indexes(entries)
    return entries


def filter_generic_values(raw_generic_items: list[dict]) -> list[GenericValue]:
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
        location = (
            FieldLocation.from_source_detail(source_detail, field=field)
            if source_detail
            else FieldLocation(fmt="json")
        )
        occurrence_index = _positive_int(item.get("occurrence_index"))
        if occurrence_index > 0:
            location = replace(location, occurrence_index=occurrence_index)
        result.append(
            GenericValue(
                field=field,
                source_relpath=source,
                location=location,
                original_value=value,
                placeholder=str(item.get("placeholder", "")).strip(),
                value_type=str(item.get("value_type", "")).strip(),
            )
        )
    return result


def _positive_int(value: object) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return 0
    return result if result > 0 else 0


def build_generic_from_entry(entry: dict) -> Optional[dict]:
    source = str(entry.get("source", "") or "").strip()
    if not source:
        return None
    final = finalize_entry(entry)
    role = entry.get("role", "config_value")
    value_type = "api_key" if role == "key" else final.get("value_type", "value")

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
            str(value_type),
            service=str(final.get("service", "")),
            url=str(final.get("url", "")),
        ),
    }
    if field_aliases:
        result["field_aliases"] = field_aliases
    if role != "key":
        result["value_type"] = value_type
    return result


__all__ = [
    "build_generic_from_entry",
    "build_scan_entries",
    "entry_field_aliases",
    "finalize_entry",
    "filter_generic_values",
    "resolve_candidate_url",
    "use_for_generic_value",
]
