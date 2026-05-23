from __future__ import annotations

from typing import Any, Iterator


REPLACE_WITH_PLACEHOLDER = "replace_with_placeholder"
EXCLUDE_VALUE = "exclude_value"


FINAL_DISPOSITIONS = (
    REPLACE_WITH_PLACEHOLDER,
    EXCLUDE_VALUE,
)


def iter_disposition_entries(reviewed_scan: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for bucket in ("url_proxy", "generic", "env_var"):
        value = reviewed_scan.get(bucket, [])
        if not isinstance(value, list):
            continue
        for index, entry in enumerate(value):
            if not isinstance(entry, dict):
                continue
            yield {
                "bucket": bucket,
                "index": index,
                "entry": entry,
            }


def reviewed_scan_has_final_dispositions(reviewed_scan: dict[str, Any]) -> bool:
    for item in iter_disposition_entries(reviewed_scan):
        entry = item["entry"]
        disposition = str(entry.get("final_disposition", "")).strip()
        if disposition not in FINAL_DISPOSITIONS:
            return False
    return True


def _entry_primary_field(entry: dict[str, Any]) -> str:
    field = str(entry.get("field", "")).strip()
    if field:
        return field
    api_key = entry.get("api_key")
    if isinstance(api_key, dict):
        field = str(api_key.get("field", "")).strip()
        if field:
            return field
    url = entry.get("url")
    if isinstance(url, dict):
        field = str(url.get("field", "")).strip()
        if field:
            return field
    return str(entry.get("use", "")).strip() or "unnamed_entry"


def _clone_with_final_disposition(entry: dict[str, Any], disposition: str) -> dict[str, Any]:
    updated = dict(entry)
    updated["final_disposition"] = disposition
    return updated


def apply_buyout_dispositions(
    reviewed_scan: dict[str, Any],
    *,
    overrides: dict[str, str],
) -> dict[str, Any]:
    updated = dict(reviewed_scan)
    for bucket in ("url_proxy", "generic", "env_var"):
        if isinstance(updated.get(bucket), list):
            updated[bucket] = list(updated[bucket])
    field_to_override = {str(key).strip(): str(value).strip() for key, value in overrides.items() if str(key).strip()}
    for item in iter_disposition_entries(updated):
        entry = dict(item["entry"])
        field = _entry_primary_field(entry)
        override = field_to_override.get(field)
        if override:
            if override not in FINAL_DISPOSITIONS:
                raise ValueError(f"unknown disposition for {field}: {override}")
            entry = _clone_with_final_disposition(entry, override)
        updated[item["bucket"]][item["index"]] = entry
    return updated


def disposition_summary(reviewed_scan: dict[str, Any]) -> dict[str, int]:
    counts = {name: 0 for name in FINAL_DISPOSITIONS}
    missing = 0
    invalid = 0
    for item in iter_disposition_entries(reviewed_scan):
        entry = item["entry"]
        disposition = str(entry.get("final_disposition", "")).strip()
        if disposition in counts:
            counts[disposition] += 1
        elif disposition:
            invalid += 1
        else:
            missing += 1
    return {
        **counts,
        "missing": missing,
        "invalid": invalid,
        "total": sum(counts.values()) + missing + invalid,
    }


__all__ = [
    "EXCLUDE_VALUE",
    "FINAL_DISPOSITIONS",
    "REPLACE_WITH_PLACEHOLDER",
    "apply_buyout_dispositions",
    "disposition_summary",
    "iter_disposition_entries",
    "reviewed_scan_has_final_dispositions",
]
