from __future__ import annotations
from typing import Optional

from packaging._shared.common.url_values import normalize_http_url_candidate


def normalized_url_entry_for_pairing(url_entry: dict) -> Optional[dict]:
    normalized_url = normalize_http_url_candidate(str(url_entry.get("value", "")).strip())
    if not normalized_url:
        return None
    normalized_entry = dict(url_entry)
    normalized_entry["value"] = normalized_url
    current_locator = str(normalized_entry.get("url", "")).strip()
    if not current_locator or normalize_http_url_candidate(current_locator):
        normalized_entry["url"] = normalize_http_url_candidate(current_locator) or normalized_url
    else:
        normalized_entry["url"] = normalized_url
    return normalized_entry


__all__ = ["normalized_url_entry_for_pairing"]
