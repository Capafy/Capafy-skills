from __future__ import annotations


def is_url_proxy_candidate(candidate: dict) -> bool:
    if not str(candidate.get("url_proxy_group", "") or "").strip():
        return False
    entry_type = str(candidate.get("entry_type", "") or "").strip()
    if entry_type == "api_key":
        return True
    value_type = str(candidate.get("value_type", "") or "").strip()
    return value_type == "url"


__all__ = [
    "is_url_proxy_candidate",
]
