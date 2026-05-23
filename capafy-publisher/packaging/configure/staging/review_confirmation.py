from __future__ import annotations

from typing import Any


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
    if api_placeholder:
        return {f"api_key.placeholder:{api_placeholder}"}
    if url_placeholder:
        return {f"url.placeholder:{url_placeholder}"}
    return set()


def _confirmed_url_proxy_identities(required_credentials_payload: dict[str, Any]) -> set[str] | None:
    if "url_proxy" not in required_credentials_payload:
        return None
    url_proxy = required_credentials_payload.get("url_proxy")
    if not isinstance(url_proxy, list):
        return None
    if not url_proxy:
        return set()
    identities: set[str] = set()
    has_stable_identity = False
    for entry in url_proxy:
        entry_identities = _url_proxy_entry_identities(entry)
        if entry_identities:
            has_stable_identity = True
        identities.update(entry_identities)


    if not has_stable_identity:
        return None
    return identities


def _confirmed_url_proxy_by_identity(required_credentials_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    url_proxy = required_credentials_payload.get("url_proxy")
    if not isinstance(url_proxy, list):
        return {}
    confirmed: dict[str, dict[str, Any]] = {}
    for entry in url_proxy:
        if not isinstance(entry, dict):
            continue
        for identity in _url_proxy_entry_identities(entry):
            confirmed[identity] = entry
    return confirmed


def _merge_confirmed_url_proxy_fields(
    entry: dict[str, Any],
    confirmed_by_identity: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    matching_confirmed: dict[str, Any] | None = None
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
    payload: dict[str, Any] | object,
    *,
    required_credentials_payload: dict[str, Any] | object,
) -> dict[str, Any] | object:
    if not isinstance(payload, dict) or not isinstance(required_credentials_payload, dict):
        return payload

    reconciled = dict(payload)
    confirmed_url_proxy = _confirmed_url_proxy_identities(required_credentials_payload)
    if confirmed_url_proxy is not None and isinstance(reconciled.get("url_proxy"), list):
        confirmed_by_identity = _confirmed_url_proxy_by_identity(required_credentials_payload)
        reconciled["url_proxy"] = [
            _merge_confirmed_url_proxy_fields(entry, confirmed_by_identity)
            for entry in reconciled.get("url_proxy", [])
            if isinstance(entry, dict) and (_url_proxy_entry_identities(entry) & confirmed_url_proxy)
        ]
    return reconciled


__all__ = [
    "reconcile_reviewed_scan_with_platform_confirmation",
]
