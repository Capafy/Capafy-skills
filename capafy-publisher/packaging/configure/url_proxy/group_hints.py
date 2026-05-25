from __future__ import annotations
from typing import Optional

from dataclasses import dataclass


@dataclass(frozen=True)
class UrlProxyPairingHints:

    env_url_hints: dict[str, str]
    service_url_hints: dict[str, str]
    value_url_hints: dict[str, str]


def is_unknown_locator(value: object) -> bool:
    return str(value or "").strip().lower() in {"", "unknown"}


def apply_url_proxy_group_hints(candidates: list[dict]) -> None:
    url_by_group: dict[str, str] = {}
    env_group_hints: dict[str, Optional[tuple[str, str]]] = {}

    def record_env_group_hint(env_name: str, group: str, url: str) -> None:
        normalized_env_name = str(env_name or "").strip()
        if not normalized_env_name or not group:
            return
        hint = (group, url)
        existing = env_group_hints.get(normalized_env_name)
        if existing is None and normalized_env_name in env_group_hints:
            return
        if existing is not None and existing != hint:
            env_group_hints[normalized_env_name] = None
            return
        env_group_hints[normalized_env_name] = hint

    for candidate in candidates:
        group = str(candidate.get("url_proxy_group", "") or "").strip()
        if not group or candidate.get("value_type") != "url":
            continue
        url = str(candidate.get("value", "") or candidate.get("local_url", "") or candidate.get("default_url", "")).strip()
        if url:
            url_by_group.setdefault(group, url)
        env_names = candidate.get("url_proxy_env_names", [])
        if isinstance(env_names, list):
            for env_name in env_names:
                record_env_group_hint(str(env_name or ""), group, url)

    for candidate in candidates:
        if candidate.get("entry_type") != "api_key":
            continue
        group = str(candidate.get("url_proxy_group", "") or "").strip()
        if not group:
            for env_name in (candidate.get("env_name"), candidate.get("field")):
                hint = env_group_hints.get(str(env_name or "").strip())
                if hint is None:
                    continue
                group, _url = hint
                candidate["url_proxy_group"] = group
                break
        if not group:
            continue
        url = url_by_group.get(group, "")
        if not url:
            continue
        if is_unknown_locator(candidate.get("default_url")):
            candidate["default_url"] = url
        if is_unknown_locator(candidate.get("local_url")):
            candidate["local_url"] = url


__all__ = ["UrlProxyPairingHints", "apply_url_proxy_group_hints", "is_unknown_locator"]
