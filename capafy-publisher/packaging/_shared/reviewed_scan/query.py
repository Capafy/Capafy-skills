from __future__ import annotations

from typing import Any


def reviewed_url_proxy_side_fields(
    reviewed_scan: dict[str, Any],
    *,
    source: str,
    side_name: str = "",
    group: str = "",
) -> set[str]:
    fields: set[str] = set()
    url_proxy = reviewed_scan.get("url_proxy", [])
    if not isinstance(url_proxy, list):
        return fields
    for entry in url_proxy:
        if not isinstance(entry, dict):
            continue
        if group and str(entry.get("url_proxy_group", "") or "").strip() != group:
            continue
        side_names = (side_name,) if side_name else ("api_key", "url")
        for current_side_name in side_names:
            side = entry.get(current_side_name)
            if not isinstance(side, dict):
                continue
            if str(side.get("source", "") or "").strip() != source:
                continue
            field = str(side.get("field", "") or "").strip()
            if field:
                fields.add(field)
    return fields


def reviewed_url_proxy_has_side_field(
    reviewed_scan: dict[str, Any],
    *,
    source: str,
    side_name: str,
    field: str,
    group: str = "",
) -> bool:
    return field in reviewed_url_proxy_side_fields(
        reviewed_scan,
        source=source,
        side_name=side_name,
        group=group,
    )


def reviewed_url_proxy_has_any_side_field(
    reviewed_scan: dict[str, Any],
    *,
    source: str,
    side_name: str,
    fields: frozenset[str],
    group: str = "",
) -> bool:
    reviewed_fields = reviewed_url_proxy_side_fields(
        reviewed_scan,
        source=source,
        side_name=side_name,
        group=group,
    )
    return bool(reviewed_fields & fields)


def reviewed_url_proxy_groups(reviewed_scan: dict[str, Any]) -> list[str]:
    groups: list[str] = []
    url_proxy = reviewed_scan.get("url_proxy", [])
    if not isinstance(url_proxy, list):
        return groups
    for entry in url_proxy:
        if not isinstance(entry, dict):
            continue
        group = str(entry.get("url_proxy_group", "") or "").strip()
        if group and group not in groups:
            groups.append(group)
    return groups


__all__ = [
    "reviewed_url_proxy_groups",
    "reviewed_url_proxy_has_any_side_field",
    "reviewed_url_proxy_has_side_field",
    "reviewed_url_proxy_side_fields",
]
