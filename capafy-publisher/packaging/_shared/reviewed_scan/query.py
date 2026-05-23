from __future__ import annotations

from typing import Any


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


__all__ = ["reviewed_url_proxy_groups"]
