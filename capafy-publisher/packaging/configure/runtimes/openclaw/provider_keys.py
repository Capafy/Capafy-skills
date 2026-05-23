from __future__ import annotations

import re
from typing import Mapping

from packaging._shared.openclaw.official_providers import OpenClawOfficialProviderSpec
from packaging.configure.sensitive.literals import looks_like_platform_managed_placeholder_value


_KEY_SPLIT = re.compile(r"[\s,;]+")
_ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def is_env_reference(value: str) -> bool:
    return bool(_ENV_NAME_RE.match(str(value or "").strip()))


def real_value(value: object) -> str:
    normalized = str(value or "").strip()
    if not normalized or looks_like_platform_managed_placeholder_value(normalized):
        return ""
    return normalized


def resolve_api_key_config_value(raw_value: str, env: Mapping[str, str]) -> str:
    value = real_value(raw_value)
    if not value:
        return ""
    if is_env_reference(value):
        return real_value(env.get(value, ""))
    return value


def _append_provider_api_key_item(
    items: list[dict[str, object]],
    *,
    env_name: str,
    value: object,
    field_aliases: list[str],
) -> None:
    normalized_value = real_value(value)
    if not normalized_value:
        return
    items.append(
        {
            "env_name": env_name,
            "value": normalized_value,
            "field_aliases": [alias for alias in field_aliases if alias],
        }
    )


def collect_provider_api_key_items(
    spec: OpenClawOfficialProviderSpec,
    env: Mapping[str, str],
) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    live = spec.live_single_env
    if live:
        value = real_value(env.get(live, ""))
        if value:
            return [{"env_name": live, "value": value, "field_aliases": [live]}]

    for n in spec.list_env_names:
        if not n:
            continue
        raw = env.get(n, "")
        for index, part in enumerate(_KEY_SPLIT.split(raw)):
            _append_provider_api_key_item(
                items,
                env_name=n,
                value=part,
                field_aliases=[n, f"{n}[{index}]"],
            )

    for n in spec.primary_env_names:
        if not n:
            continue
        _append_provider_api_key_item(
            items,
            env_name=n,
            value=env.get(n, ""),
            field_aliases=[n],
        )

    for normalized_prefix in spec.env_prefixes:
        if not normalized_prefix:
            continue
        for env_name in sorted(env):
            if not env_name.startswith(normalized_prefix):
                continue
            _append_provider_api_key_item(
                items,
                env_name=env_name,
                value=env.get(env_name, ""),
                field_aliases=[env_name],
            )

    for n in spec.fallback_env_names:
        if not n:
            continue
        _append_provider_api_key_item(
            items,
            env_name=n,
            value=env.get(n, ""),
            field_aliases=[n],
        )

    return dedupe_key_items(items)


def dedupe_key_items(items: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, object]] = []
    for item in items:
        value = str(item.get("value", "") or "").strip()
        env_name = str(item.get("env_name", "") or "").strip()
        identity = (env_name, value)
        if not value or identity in seen:
            continue
        seen.add(identity)
        result.append(item)
    return result


__all__ = [
    "collect_provider_api_key_items",
    "dedupe_key_items",
    "is_env_reference",
    "real_value",
    "resolve_api_key_config_value",
]
