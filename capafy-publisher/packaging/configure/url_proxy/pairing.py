from __future__ import annotations

from packaging.configure.generic_keys.builder import build_generic_from_entry
from packaging.configure.url_proxy.entry_converters import (
    build_url_proxy_entry as _build_url_proxy_entry,
    url_proxy_entry_to_pair,
)
from packaging.configure.url_proxy.group_hints import apply_url_proxy_group_hints
from packaging.configure.url_proxy.pairing_entries import (
    normalized_url_entry_for_pairing,
)
from packaging.configure.url_proxy.predicates import is_url_proxy_candidate


def _append_generic(generic: list[dict], entry: dict) -> None:
    generic_entry = build_generic_from_entry(entry)
    if generic_entry is not None:
        generic.append(generic_entry)


def pair_url_proxy_entries(
    entries: dict[str, dict],
) -> tuple[list[dict], list[dict]]:
    grouped_keys: dict[str, list[tuple[str, dict]]] = {}
    grouped_urls: dict[str, list[tuple[str, dict]]] = {}
    generic: list[dict] = []

    for value, entry in entries.items():
        role = entry.get("role", "config_value")
        group = str(entry.get("url_proxy_group", "") or "").strip()
        if group and role == "key":
            grouped_keys.setdefault(group, []).append((value, entry))
            continue
        if group and role == "url":
            grouped_urls.setdefault(group, []).append((value, entry))
            continue
        _append_generic(generic, entry)

    url_proxy: list[dict] = []
    for group in sorted(set(grouped_keys) | set(grouped_urls)):
        key_entries = grouped_keys.get(group, [])
        url_entries = grouped_urls.get(group, [])
        if not key_entries or not url_entries:
            for _value, entry in [*key_entries, *url_entries]:
                _append_generic(generic, entry)
            continue

        normalized_url_entries: list[dict] = []
        extra_url_entries: list[dict] = []
        _first_url_value, first_url_entry = url_entries[0]
        first_normalized_url_entry = normalized_url_entry_for_pairing(first_url_entry)
        if first_normalized_url_entry is None:
            for _value, entry in [*key_entries, *url_entries]:
                _append_generic(generic, entry)
            continue
        first_url_value = str(first_normalized_url_entry.get("value", "")).strip()
        normalized_url_entries.append(first_normalized_url_entry)
        for _value, url_entry in url_entries[1:]:
            normalized_url_entry = normalized_url_entry_for_pairing(url_entry)
            if normalized_url_entry is None:
                extra_url_entries.append(url_entry)
                continue
            if str(normalized_url_entry.get("value", "")).strip() != first_url_value:
                extra_url_entries.append(url_entry)
                continue
            normalized_url_entries.append(normalized_url_entry)

        pair_count = max(len(key_entries), len(normalized_url_entries))
        for index in range(pair_count):
            _key_value, key_entry = key_entries[index % len(key_entries)]
            url_entry = normalized_url_entries[index % len(normalized_url_entries)]
            if index > 0 and not str(url_entry.get("occurrence_id", "")).strip():
                url_entry = dict(url_entry)
                url_entry["occurrence_id"] = f"{group}[{index}]"
            if index > 0 and not str(key_entry.get("occurrence_id", "")).strip():
                key_entry = dict(key_entry)
                key_entry["occurrence_id"] = f"{group}[{index}]"
            url_proxy.append(_build_url_proxy_entry(key_entry, url_entry))
        for extra_url_entry in extra_url_entries:
            _append_generic(generic, extra_url_entry)

    return url_proxy, generic


__all__ = [
    "apply_url_proxy_group_hints",
    "is_url_proxy_candidate",
    "pair_url_proxy_entries",
    "url_proxy_entry_to_pair",
]
