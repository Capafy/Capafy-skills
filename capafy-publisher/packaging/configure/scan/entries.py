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


def _assign_scan_entry_occurrence_indexes(entries: dict[str, dict]) -> None:
    counters: dict[tuple[str, str, str], int] = {}
    for entry in entries.values():
        key = _occurrence_identity(entry)
        counters[key] = counters.get(key, 0) + 1
        entry["occurrence_index"] = counters[key]


def build_scan_entries(
    candidates: list[dict],
    env_url_hints: dict[str, str],
    service_url_hints: dict[str, str],
    value_url_hints: dict[str, str],
) -> dict[str, dict]:
    entries: dict[str, dict] = {}

    for candidate_index, candidate in enumerate(candidates):
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

        url_proxy_group = str(candidate.get("url_proxy_group", "") or "").strip()
        if url_proxy_group:
            entry["url_proxy_group"] = url_proxy_group





        entry_key = f"{url_proxy_group}\0{value}\0{candidate_index}" if url_proxy_group else f"{value}\0{candidate_index}"
        entries[entry_key] = entry

    _assign_scan_entry_occurrence_indexes(entries)
    return entries


def build_scan_groups(url_proxy: list[dict], generic: list[dict]) -> dict[str, list[dict]]:

    for index, entry in enumerate(url_proxy, start=1):
        entry["index"] = index
    for index, entry in enumerate(generic, start=1):
        entry["index"] = index

    return {
        "url_proxy": url_proxy,
        "generic": generic,
    }


__all__ = ["build_scan_entries", "build_scan_groups"]
