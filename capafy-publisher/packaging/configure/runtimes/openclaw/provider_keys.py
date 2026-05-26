from __future__ import annotations

import re
from typing import Mapping

from packaging._shared.openclaw.official_providers import OpenClawOfficialProviderSpec
from packaging.configure.env_values import (
    env_reference_name,
    usable_env_value,
    usable_process_env_value,
)


_KEY_SPLIT = re.compile(r"[\s,;]+")


def _append_provider_api_key_item(
    items: list[dict[str, object]],
    *,
    env_name: str,
    value: object,
    field_aliases: list[str],
) -> None:
    normalized_value = usable_env_value(value)
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
        value = usable_process_env_value(env, live)
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


def collect_provider_api_key_items_by_priority(
    spec: OpenClawOfficialProviderSpec,
    *,
    api_key: object,
    auth_profile_values: list[str],
    env: Mapping[str, str],
) -> list[dict[str, object]]:
    configured_key = usable_env_value(api_key)
    if configured_key:
        env_name = env_reference_name(configured_key)
        if not env_name:
            return [{"env_name": "", "value": configured_key, "field_aliases": []}]
        resolved = usable_env_value(env.get(env_name, ""))
        if resolved:
            return [{"env_name": env_name, "value": resolved, "field_aliases": [env_name]}]

    items: list[dict[str, object]] = []
    for value in auth_profile_values:
        _append_provider_api_key_item(
            items,
            env_name="",
            value=value,
            field_aliases=[],
        )
    if items:
        return dedupe_key_items(items)

    return collect_provider_api_key_items(spec, env)


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
    "collect_provider_api_key_items_by_priority",
    "dedupe_key_items",
]
