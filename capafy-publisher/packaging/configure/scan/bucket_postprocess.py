from __future__ import annotations

from packaging.configure.generic_keys.builder import build_generic_from_entry
from packaging.configure.scan.entries import build_scan_entries, build_scan_groups


def dedupe_scan_results(
    candidates: list[dict],
    env_url_hints: dict[str, str],
    service_url_hints: dict[str, str],
    value_url_hints: dict[str, str],
) -> dict[str, list[dict]]:
    entries = build_scan_entries(candidates, env_url_hints, service_url_hints, value_url_hints)
    generic_entries = [
        generic_entry
        for entry in entries.values()
        if (generic_entry := build_generic_from_entry(entry)) is not None
    ]
    return build_scan_groups(
        [],
        generic_entries,
    )


__all__ = [
    "build_scan_entries",
    "build_scan_groups",
    "dedupe_scan_results",
]
