from __future__ import annotations

from typing import Any, Optional, Union


def _managed_item_identity_value(item: object, key: str) -> str:
    if not isinstance(item, dict):
        return ""
    return str(item.get(key, "") or "").strip()


def _url_proxy_entry_identities(entry: object) -> set[str]:
    if not isinstance(entry, dict):
        return set()
    api_key = entry.get("api_key")
    url = entry.get("url")
    api_placeholder = _managed_item_identity_value(api_key, "placeholder")
    url_placeholder = _managed_item_identity_value(url, "placeholder")
    identities: set[str] = set()
    if api_placeholder:
        identities.add(f"api_key.placeholder:{api_placeholder}")
    if url_placeholder:
        identities.add(f"url.placeholder:{url_placeholder}")
    return identities


def _confirmed_url_proxy_by_identity(
    required_credentials_payload: dict[str, Any],
) -> Optional[dict[str, dict[str, Any]]]:
    if "url_proxy" not in required_credentials_payload:
        return None
    url_proxy = required_credentials_payload.get("url_proxy")
    if not isinstance(url_proxy, list):
        return None
    if not url_proxy:
        return {}
    confirmed: dict[str, dict[str, Any]] = {}
    has_stable_identity = False
    for entry in url_proxy:
        entry_identities = _url_proxy_entry_identities(entry)
        if entry_identities:
            has_stable_identity = True
        if isinstance(entry, dict):
            for identity in entry_identities:
                confirmed[identity] = entry
    if not has_stable_identity:
        return None
    return confirmed


def _merge_confirmed_url_proxy_fields(
    entry: dict[str, Any],
    confirmed_by_identity: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    matching_confirmed: Optional[dict[str, Any]] = None
    for identity in _url_proxy_entry_identities(entry):
        if identity in confirmed_by_identity:
            matching_confirmed = confirmed_by_identity[identity]
            break
    if matching_confirmed is None:
        return dict(entry)

    merged = dict(entry)
    for key in ("model", "api_format"):
        value = str(matching_confirmed.get(key, "") or "").strip()
        if value:
            merged[key] = value
    return merged


def reconcile_reviewed_scan_with_platform_confirmation(
    payload: Union[dict[str, Any], object],
    *,
    required_credentials_payload: Union[dict[str, Any], object],
) -> Union[dict[str, Any], object]:
    if not isinstance(payload, dict) or not isinstance(required_credentials_payload, dict):
        return payload

    reconciled = dict(payload)
    confirmed_by_identity = _confirmed_url_proxy_by_identity(required_credentials_payload)
    if confirmed_by_identity is not None and isinstance(reconciled.get("url_proxy"), list):
        reconciled["url_proxy"] = [
            _merge_confirmed_url_proxy_fields(entry, confirmed_by_identity)
            for entry in reconciled.get("url_proxy", [])
            if isinstance(entry, dict) and (_url_proxy_entry_identities(entry) & confirmed_by_identity.keys())
        ]
    return reconciled


__all__ = [
    "reconcile_reviewed_scan_with_platform_confirmation",
]
