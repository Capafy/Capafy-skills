from __future__ import annotations

from packaging.configure.sensitive.placeholders import split_source

from .entry_finalize import resolve_candidate_url


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
    service_url_hints: dict[str, str],
    value_url_hints: dict[str, str],
) -> list[dict]:
    entries: list[dict] = []

    for candidate in candidates:
        value = candidate["value"]

        resolved_url = resolve_candidate_url(candidate, env_url_hints, service_url_hints, value_url_hints)

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


__all__ = ["build_scan_entries"]
