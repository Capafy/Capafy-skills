from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Mapping, Optional, TYPE_CHECKING

from packaging.configure.env_values import (
    env_reference_name,
    usable_env_value,
)
from packaging.configure.runtimes.openclaw.official_providers import (
    OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME,
    match_openclaw_builtin_model_provider,
)
from packaging.configure.runtimes.openclaw.provider_keys import collect_provider_api_key_items
from packaging.configure.runtimes.openclaw.provider_usage import path_likely_contains_openclaw_model_ref

if TYPE_CHECKING:
    from packaging.configure.staging.env_preprocess import RuntimeEnvContext


OPENCLAW_CONFIG_REL_SOURCE = ".openclaw/openclaw.json"
_OPENCLAW_ENV_TEMPLATE_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _openclaw_config_env(payload: dict[str, object]) -> dict[str, str]:
    env = payload.get("env")
    if not isinstance(env, dict):
        return {}
    result: dict[str, str] = {}
    for name, value in env.items():
        normalized_name = str(name or "").strip()
        if normalized_name and isinstance(value, str):
            result[normalized_name] = value
    return result


def resolve_openclaw_config_env(
    *,
    payload: dict[str, object],
    dotenv_env: Optional[dict[str, str]] = None,
    process_env: Optional[Mapping[str, str]] = None,
) -> dict[str, str]:
    merged = _openclaw_config_env(payload)
    merged.update(dotenv_env or {})
    merged.update(
        {
            str(name).strip(): value
            for name, value in (process_env or {}).items()
            if str(name).strip() and isinstance(value, str)
        }
    )
    return merged


def _resolve_openclaw_env_template_value(
    value: str,
    config_env: Mapping[str, str],
    consumed_env_names: set[str],
) -> str:
    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        replacement = usable_env_value(config_env.get(name, ""))
        if not replacement:
            return match.group(0)
        consumed_env_names.add(name)
        return replacement

    return _OPENCLAW_ENV_TEMPLATE_RE.sub(_replace, value)


def _resolve_openclaw_env_templates(
    node: object,
    config_env: Mapping[str, str],
    consumed_env_names: set[str],
) -> int:
    rewrites = 0
    if isinstance(node, dict):
        items = node.items()
    elif isinstance(node, list):
        items = enumerate(node)
    else:
        return 0

    for key, value in items:
        if isinstance(value, str):
            updated_value = _resolve_openclaw_env_template_value(value, config_env, consumed_env_names)
            if updated_value == value:
                continue
            node[key] = updated_value
            rewrites += 1
            continue
        rewrites += _resolve_openclaw_env_templates(value, config_env, consumed_env_names)
    return rewrites


def materialize_official_provider_env_keys(
    providers: dict[str, object],
    config_env: dict[str, str],
) -> tuple[int, set[str]]:
    if not config_env:
        return 0, set()
    rewrites = 0
    consumed_env_names: set[str] = set()
    for provider_name, spec in OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME.items():
        provider = providers.get(provider_name)
        if not isinstance(provider, dict):
            continue
        if str(provider.get("api", "") or "").strip() != spec.api:
            continue
        key_items = collect_provider_api_key_items(spec, config_env)
        env_item = key_items[0] if key_items else None
        env_key = str(env_item.get("value", "") or "").strip() if env_item else ""
        if not env_key or usable_env_value(provider.get("apiKey", "")):
            continue
        provider["apiKey"] = env_key
        env_name = str(env_item.get("env_name", "") or "").strip() if env_item else ""
        if env_name:
            consumed_env_names.add(env_name)
        rewrites += 1
    return rewrites, consumed_env_names


def materialize_provider_env_references(
    providers: dict[str, object],
    config_env: dict[str, str],
) -> tuple[int, set[str]]:
    if not config_env:
        return 0, set()
    rewrites = 0
    consumed_env_names: set[str] = set()
    for provider in providers.values():
        if not isinstance(provider, dict):
            continue
        env_name = env_reference_name(provider.get("apiKey", ""))
        if not env_name:
            continue
        env_value = usable_env_value(config_env.get(env_name, ""))
        if not env_value:
            continue
        provider["apiKey"] = env_value
        consumed_env_names.add(env_name)
        rewrites += 1
    return rewrites, consumed_env_names


def drop_consumed_config_env(payload: dict[str, object], consumed_env_names: set[str]) -> int:
    if not consumed_env_names:
        return 0
    env = payload.get("env")
    if not isinstance(env, dict):
        return 0
    removed = 0
    for env_name in sorted(consumed_env_names):
        if env_name in env:
            env.pop(env_name, None)
            removed += 1
    if not env:
        payload.pop("env", None)
    return removed


def _provider_env_names(providers: dict[str, object]) -> set[str]:
    names: set[str] = set()
    for provider_name, provider in providers.items():
        if not isinstance(provider, dict):
            continue
        api_key = str(provider.get("apiKey", "") or "").strip()
        env_name = env_reference_name(api_key)
        if env_name:
            names.add(env_name)
        spec = OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME.get(provider_name)
        if spec is None:
            continue
        provider_api = str(provider.get("api", "") or "").strip()
        if provider_api and provider_api != spec.api:
            continue
        names.update(spec.exact_env_keys)
    return names


def _builtin_model_env_names(
    node: object,
    *,
    path_parts: tuple[str, ...] = (),
) -> set[str]:
    if isinstance(node, dict):
        names: set[str] = set()
        for key, value in node.items():
            names.update(_builtin_model_env_names(value, path_parts=(*path_parts, str(key))))
        return names
    if isinstance(node, list):
        names: set[str] = set()
        for index, value in enumerate(node):
            names.update(_builtin_model_env_names(value, path_parts=(*path_parts, str(index))))
        return names
    if not isinstance(node, str) or not path_likely_contains_openclaw_model_ref(path_parts):
        return set()
    matched = match_openclaw_builtin_model_provider(node)
    if matched is None:
        return set()
    spec, _model_name = matched
    return set(spec.exact_env_keys)


def _dotenv_env_names_for_payload(payload: dict[str, object], config_text: str = "") -> set[str]:
    names: set[str] = set()
    models = payload.get("models")
    if isinstance(models, dict):
        providers = models.get("providers")
        if isinstance(providers, dict):
            names.update(_provider_env_names(providers))
    names.update(_builtin_model_env_names(payload))
    names.update(_OPENCLAW_ENV_TEMPLATE_RE.findall(config_text))
    return {name for name in names if env_reference_name(name)}


def collect_openclaw_staged_dotenv_env(
    staging_root: Path,
    config_text: str,
    *,
    env_context: "RuntimeEnvContext",
) -> dict[str, str]:
    try:
        payload = json.loads(config_text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}

    names = _dotenv_env_names_for_payload(payload, config_text)
    if not names:
        return {}

    return env_context.staged_dotenv_values_for_consumer(
        Path(staging_root),
        consumer_relpath=OPENCLAW_CONFIG_REL_SOURCE,
        names=frozenset(names),
    )


def resolve_openclaw_staged_env_templates(
    staging_root: Path,
    *,
    env_context: "RuntimeEnvContext",
) -> frozenset[str]:
    root = Path(staging_root)
    config_path = root / OPENCLAW_CONFIG_REL_SOURCE
    try:
        config_text = config_path.read_text(encoding="utf-8")
        payload = json.loads(config_text)
    except (OSError, json.JSONDecodeError):
        return frozenset()
    if not isinstance(payload, dict):
        return frozenset()

    dotenv_relpaths = env_context.staged_dotenv_relpaths_for_consumer(OPENCLAW_CONFIG_REL_SOURCE)
    dotenv_env = collect_openclaw_staged_dotenv_env(root, config_text, env_context=env_context)
    template_env_names = frozenset(_OPENCLAW_ENV_TEMPLATE_RE.findall(config_text))
    merged_process_env = env_context.env_for_names(template_env_names)
    config_env = resolve_openclaw_config_env(
        payload=payload,
        dotenv_env=dotenv_env,
        process_env=merged_process_env,
    )
    consumed_env_names: set[str] = set()
    rewrites = _resolve_openclaw_env_templates(
        payload,
        config_env,
        consumed_env_names,
    )
    if rewrites <= 0:
        return frozenset()

    drop_consumed_config_env(payload, consumed_env_names)
    env_context.consume_staged_dotenv_names(
        root,
        relpaths=dotenv_relpaths,
        names=frozenset(consumed_env_names),
    )
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return frozenset(consumed_env_names)


__all__ = [
    "OPENCLAW_CONFIG_REL_SOURCE",
    "collect_openclaw_staged_dotenv_env",
    "drop_consumed_config_env",
    "materialize_official_provider_env_keys",
    "materialize_provider_env_references",
    "resolve_openclaw_config_env",
    "resolve_openclaw_staged_env_templates",
]
