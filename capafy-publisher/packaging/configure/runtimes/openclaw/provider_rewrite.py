from __future__ import annotations
from typing import Mapping, Optional, TYPE_CHECKING

import json
import re
from pathlib import Path

from packaging._shared.openclaw.official_providers import (
    OpenClawOfficialProviderSpec,
    OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME,
    find_openclaw_official_provider_by_marker,
    match_openclaw_builtin_model_provider,
)
from packaging._shared.common.url_values import normalize_http_url_candidate
from packaging.configure.runtimes.openclaw.provider_keys import (
    collect_provider_api_key_items,
)
from packaging.configure.env_values import (
    env_reference_name,
    usable_env_value,
)
from packaging.configure.runtimes.openclaw.provider_usage import (
    openclaw_model_id_from_entry,
    path_likely_contains_openclaw_model_ref,
)
from packaging.configure.sensitive.literals import looks_like_platform_managed_placeholder_value
from packaging.configure.sensitive.placeholders import build_placeholder
from packaging._shared.common.json_io import clone_json_value

if TYPE_CHECKING:
    from packaging.configure.staging.env_preprocess import RuntimeEnvContext


_DEFAULT_MODELS_MODE = "merge"
_OPENCLAW_CONFIG_REL_SOURCE = ".openclaw/openclaw.json"
_OPENCLAW_ENV_TEMPLATE_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_DEFAULT_MODEL_TEMPLATE = {
    "reasoning": True,
    "input": ["text", "image"],
    "cost": {
        "input": 0,
        "output": 0,
        "cacheRead": 0,
        "cacheWrite": 0,
    },
    "contextWindow": 200000,
    "maxTokens": 64000,
    "headers": {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json",
    },
}


def _official_provider_placeholder(
    spec: OpenClawOfficialProviderSpec,
    provider_name: str,
    *,
    field: str,
    value_type: str = "",
) -> str:
    base_url = spec.base_url
    return build_placeholder(
        spec.service,
        _OPENCLAW_CONFIG_REL_SOURCE,
        field=f"models.providers.{provider_name}.{field}",
        locator=base_url,
        value_type=value_type,
    )


def _discover_model_template(payload: dict[str, object]) -> Optional[dict[str, object]]:
    models = payload.get("models")
    if not isinstance(models, dict):
        return None
    providers = models.get("providers")
    if not isinstance(providers, dict):
        return None
    for provider_payload in providers.values():
        if not isinstance(provider_payload, dict):
            continue
        model_entries = provider_payload.get("models")
        if not isinstance(model_entries, list) or not model_entries:
            continue
        first_entry = model_entries[0]
        if isinstance(first_entry, dict):
            return clone_json_value(first_entry)
    return None


def _build_model_entry(model_name: str, template: Optional[dict[str, object]]) -> dict[str, object]:
    entry_template = clone_json_value(template) if isinstance(template, dict) else clone_json_value(_DEFAULT_MODEL_TEMPLATE)
    if not isinstance(entry_template, dict):
        entry_template = clone_json_value(_DEFAULT_MODEL_TEMPLATE)
    entry_template["id"] = model_name
    entry_template["name"] = model_name
    return entry_template


def _provider_name_for_spec(
    spec: OpenClawOfficialProviderSpec,
    providers: dict[str, object],
    assigned_names: dict[str, str],
) -> str:
    family = spec.family
    if family in assigned_names:
        return assigned_names[family]

    if isinstance(providers.get(spec.provider_name), dict):
        assigned_names[family] = spec.provider_name
        return spec.provider_name

    candidate = spec.provider_name
    suffix = 2
    while True:
        existing = providers.get(candidate)
        if not isinstance(existing, dict):
            assigned_names[family] = candidate
            return candidate
        if _provider_payload_matches_spec(existing, spec, provider_name=candidate):
            assigned_names[family] = candidate
            return candidate
        candidate = f"{spec.provider_name}_{suffix}"
        suffix += 1


def _provider_alias_matches_spec(provider_name: str, payload: dict[str, object]) -> Optional[OpenClawOfficialProviderSpec]:
    spec = find_openclaw_official_provider_by_marker(provider_name)
    if spec is None:
        return None
    api = str(payload.get("api", "") or "").strip()
    if api and api != spec.api:
        return None
    return spec


def _merge_provider_models(target: dict[str, object], source: dict[str, object]) -> bool:
    source_models = source.get("models")
    if not isinstance(source_models, list):
        return False
    target_models = target.get("models")
    if not isinstance(target_models, list):
        target_models = []
        target["models"] = target_models
    seen = {
        key
        for key in (openclaw_model_id_from_entry(item) for item in target_models)
        if key
    }
    changed = False
    for item in source_models:
        key = openclaw_model_id_from_entry(item)
        if key and key in seen:
            continue
        target_models.append(clone_json_value(item))
        if key:
            seen.add(key)
        changed = True
    return changed


def _merge_official_provider_alias(
    target: dict[str, object],
    source: dict[str, object],
    spec: OpenClawOfficialProviderSpec,
) -> bool:
    changed = False
    for key, value in source.items():
        if key in {"api", "apiKey", "baseUrl", "models"}:
            continue
        if key not in target:
            target[key] = clone_json_value(value)
            changed = True

    source_key = str(source.get("apiKey", "") or "").strip()
    target_key = str(target.get("apiKey", "") or "").strip()
    if source_key and (not target_key or looks_like_platform_managed_placeholder_value(target_key)):
        target["apiKey"] = source_key
        changed = True

    source_url = str(source.get("baseUrl", "") or "").strip()
    target_url = str(target.get("baseUrl", "") or "").strip()
    if source_url and (
        not target_url
        or looks_like_platform_managed_placeholder_value(target_url)
        or not normalize_http_url_candidate(target_url)
    ):
        target["baseUrl"] = source_url
        changed = True

    changed = _merge_provider_models(target, source) or changed
    if target.get("api") != spec.api:
        target["api"] = spec.api
        changed = True
    return changed


def _canonicalize_official_provider_aliases(providers: dict[str, object]) -> int:
    rewrites = 0
    for provider_name in list(providers):
        provider = providers.get(provider_name)
        if not isinstance(provider, dict):
            continue
        spec = _provider_alias_matches_spec(provider_name, provider)
        if spec is None:
            continue

        canonical_name = spec.provider_name
        canonical_provider = providers.get(canonical_name)
        if not isinstance(canonical_provider, dict):
            providers[canonical_name] = provider
            providers.pop(provider_name, None)
            if provider.get("api") != spec.api:
                provider["api"] = spec.api
            rewrites += 1
            continue

        if _merge_official_provider_alias(canonical_provider, provider, spec):
            rewrites += 1
        providers.pop(provider_name, None)
        rewrites += 1
    return rewrites


def _provider_payload_matches_spec(
    payload: dict[str, object],
    spec: OpenClawOfficialProviderSpec,
    *,
    provider_name: str,
) -> bool:
    if str(payload.get("api", "")).strip() != spec.api:
        return False

    api_key = str(payload.get("apiKey", "") or "").strip()
    accepted_keys = {
        spec.default_env_key,
        _official_provider_placeholder(spec, provider_name, field="apiKey"),
    }
    accepted_keys.update(item for item in spec.exact_env_keys if item)
    key_matches = (
        not api_key
        or api_key in accepted_keys
        or looks_like_platform_managed_placeholder_value(api_key)
    )

    base_url = str(payload.get("baseUrl", "") or "").strip()
    accepted_urls = {
        spec.base_url,
        _official_provider_placeholder(spec, provider_name, field="baseUrl", value_type="url"),
    }
    url_matches = (
        not base_url
        or base_url in accepted_urls
        or looks_like_platform_managed_placeholder_value(base_url)
    )
    return key_matches and url_matches


def _ensure_provider_payload(
    providers: dict[str, object],
    provider_name: str,
    *,
    spec: OpenClawOfficialProviderSpec,
    model_name: str,
    model_template: Optional[dict[str, object]],
) -> None:
    provider_payload = providers.get(provider_name)
    if not isinstance(provider_payload, dict):
        provider_payload = {}
        providers[provider_name] = provider_payload

    provider_payload["api"] = spec.api
    api_key = str(provider_payload.get("apiKey", "") or "").strip()
    if not api_key or looks_like_platform_managed_placeholder_value(api_key):
        provider_payload["apiKey"] = _official_provider_placeholder(spec, provider_name, field="apiKey")
    base_url = str(provider_payload.get("baseUrl", "") or "").strip()
    if (
        not base_url
        or looks_like_platform_managed_placeholder_value(base_url)
        or not normalize_http_url_candidate(base_url)
    ):
        provider_payload["baseUrl"] = _official_provider_placeholder(
            spec,
            provider_name,
            field="baseUrl",
            value_type="url",
        )

    model_entries = provider_payload.get("models")
    if not isinstance(model_entries, list):
        model_entries = []
        provider_payload["models"] = model_entries

    if any(isinstance(item, dict) and str(item.get("id", "")).strip() == model_name for item in model_entries):
        return
    model_entries.append(_build_model_entry(model_name, model_template))


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


def _resolve_openclaw_config_env(
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


def _materialize_official_provider_env_keys(
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


def _materialize_provider_env_references(
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


def _drop_consumed_config_env(payload: dict[str, object], consumed_env_names: set[str]) -> int:
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


def _collect_openclaw_staged_dotenv_env(
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
        consumer_relpath=_OPENCLAW_CONFIG_REL_SOURCE,
        names=frozenset(names),
    )


def resolve_openclaw_staged_env_templates(
    staging_root: Path,
    *,
    env_context: "RuntimeEnvContext",
) -> frozenset[str]:
    root = Path(staging_root)
    config_path = root / _OPENCLAW_CONFIG_REL_SOURCE
    try:
        config_text = config_path.read_text(encoding="utf-8")
        payload = json.loads(config_text)
    except (OSError, json.JSONDecodeError):
        return frozenset()
    if not isinstance(payload, dict):
        return frozenset()

    dotenv_relpaths = env_context.staged_dotenv_relpaths_for_consumer(_OPENCLAW_CONFIG_REL_SOURCE)
    dotenv_env = _collect_openclaw_staged_dotenv_env(root, config_text, env_context=env_context)
    template_env_names = frozenset(_OPENCLAW_ENV_TEMPLATE_RE.findall(config_text))
    merged_process_env = env_context.env_for_names(template_env_names)
    config_env = _resolve_openclaw_config_env(
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

    _drop_consumed_config_env(payload, consumed_env_names)
    env_context.consume_staged_dotenv_names(
        root,
        relpaths=dotenv_relpaths,
        names=frozenset(consumed_env_names),
    )
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return frozenset(consumed_env_names)


def _rewrite_builtin_model_refs(
    node: object,
    *,
    path_parts: tuple[str, ...],
    providers: dict[str, object],
    assigned_names: dict[str, str],
    model_template: Optional[dict[str, object]],
) -> tuple[object, int]:
    if isinstance(node, dict):
        updated: dict[str, object] = {}
        rewrites = 0
        for key, value in node.items():
            next_value, next_rewrites = _rewrite_builtin_model_refs(
                value,
                path_parts=(*path_parts, str(key)),
                providers=providers,
                assigned_names=assigned_names,
                model_template=model_template,
            )
            updated[str(key)] = next_value
            rewrites += next_rewrites
        return updated, rewrites

    if isinstance(node, list):
        updated_items: list[object] = []
        rewrites = 0
        for index, value in enumerate(node):
            next_value, next_rewrites = _rewrite_builtin_model_refs(
                value,
                path_parts=(*path_parts, str(index)),
                providers=providers,
                assigned_names=assigned_names,
                model_template=model_template,
            )
            updated_items.append(next_value)
            rewrites += next_rewrites
        return updated_items, rewrites

    if not isinstance(node, str) or not path_likely_contains_openclaw_model_ref(path_parts):
        return node, 0

    matched = match_openclaw_builtin_model_provider(node)
    if matched is None:
        return node, 0
    spec, model_name = matched
    if not model_name:
        return node, 0

    provider_name = _provider_name_for_spec(
        spec,
        providers,
        assigned_names,
    )
    _ensure_provider_payload(
        providers,
        provider_name,
        spec=spec,
        model_name=model_name,
        model_template=model_template,
    )
    return f"{provider_name}/{model_name}", 1


def rewrite_openclaw_builtin_models_as_explicit_providers(
    config_text: str,
    *,
    staging_root: Path,
    env_context: "RuntimeEnvContext",
) -> tuple[str, int]:
    try:
        payload = json.loads(config_text)
    except json.JSONDecodeError:
        return config_text, 0
    if not isinstance(payload, dict):
        return config_text, 0

    dotenv_env = _collect_openclaw_staged_dotenv_env(staging_root, config_text, env_context=env_context)
    config_env = _resolve_openclaw_config_env(
        payload=payload,
        dotenv_env=dotenv_env,
    )
    consumed_env_names: set[str] = set()

    model_template = _discover_model_template(payload)
    models = payload.get("models")
    if not isinstance(models, dict):
        models = {}
        payload["models"] = models
    providers = models.get("providers")
    if not isinstance(providers, dict):
        providers = {}
        models["providers"] = providers
    alias_rewrites = _canonicalize_official_provider_aliases(providers)

    assigned_names: dict[str, str] = {}
    rewritten_payload, rewrite_count = _rewrite_builtin_model_refs(
        payload,
        path_parts=(),
        providers=providers,
        assigned_names=assigned_names,
        model_template=model_template,
    )
    official_key_rewrites, provider_key_consumed_env_names = _materialize_official_provider_env_keys(providers, config_env)
    provider_ref_rewrites, provider_ref_consumed_env_names = _materialize_provider_env_references(providers, config_env)
    consumed_env_names.update(provider_key_consumed_env_names)
    consumed_env_names.update(provider_ref_consumed_env_names)
    provider_key_rewrites = official_key_rewrites + provider_ref_rewrites
    if consumed_env_names:
        env_context.consume_staged_dotenv_names(
            staging_root,
            relpaths=env_context.staged_dotenv_relpaths_for_consumer(_OPENCLAW_CONFIG_REL_SOURCE),
            names=frozenset(consumed_env_names),
        )
    if provider_key_rewrites or alias_rewrites:
        rewritten_payload["models"] = clone_json_value(models)
    if consumed_env_names:
        _drop_consumed_config_env(rewritten_payload, consumed_env_names)
    if rewrite_count <= 0:
        total_rewrites = provider_key_rewrites + alias_rewrites
        if total_rewrites <= 0:
            return config_text, 0
        return json.dumps(rewritten_payload, ensure_ascii=False, indent=2) + "\n", total_rewrites
    if not str(models.get("mode", "")).strip():
        models["mode"] = _DEFAULT_MODELS_MODE
    rewritten_payload["models"] = clone_json_value(models)
    return json.dumps(rewritten_payload, ensure_ascii=False, indent=2) + "\n", (
        rewrite_count + provider_key_rewrites + alias_rewrites
    )


__all__ = [
    "resolve_openclaw_staged_env_templates",
    "rewrite_openclaw_builtin_models_as_explicit_providers",
]
