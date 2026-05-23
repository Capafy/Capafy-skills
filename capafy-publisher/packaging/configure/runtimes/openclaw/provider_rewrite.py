from __future__ import annotations

import json
from pathlib import Path

from packaging._shared.openclaw.official_providers import (
    OpenClawOfficialProviderSpec,
    OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME,
    match_openclaw_builtin_model_provider,
)
from packaging.configure.runtimes.openclaw.provider_keys import (
    collect_provider_api_key_items,
    is_env_reference,
    real_value,
    resolve_api_key_config_value,
)
from packaging.configure.sensitive.literals import looks_like_platform_managed_placeholder_value
from packaging.configure.sensitive.placeholders import build_placeholder
from packaging._shared.common.json_io import clone_json_value
from packaging.configure.url_proxy.scanner_utils import UrlProxyFieldSet, scan_dotenv


_DEFAULT_MODELS_MODE = "merge"
_OPENCLAW_CONFIG_REL_SOURCE = ".openclaw/openclaw.json"
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


def _match_builtin_provider_spec(model_ref: str) -> tuple[OpenClawOfficialProviderSpec, str] | None:
    return match_openclaw_builtin_model_provider(model_ref)


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


def _discover_model_template(payload: dict[str, object]) -> dict[str, object] | None:
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


def _build_model_entry(model_name: str, template: dict[str, object] | None) -> dict[str, object]:
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


def _path_likely_contains_model_ref(path_parts: tuple[str, ...]) -> bool:
    lowered = [part.lower() for part in path_parts]
    if "memorysearch" in lowered:
        return False
    return any("model" in part or "fallback" in part for part in lowered)


def _ensure_provider_payload(
    providers: dict[str, object],
    provider_name: str,
    *,
    spec: OpenClawOfficialProviderSpec,
    model_name: str,
    model_template: dict[str, object] | None,
) -> None:
    provider_payload = providers.get(provider_name)
    if not isinstance(provider_payload, dict):
        provider_payload = {}
        providers[provider_name] = provider_payload

    provider_payload["api"] = spec.api
    provider_payload["apiKey"] = _official_provider_placeholder(spec, provider_name, field="apiKey")
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


def _official_provider_env_item(
    spec: OpenClawOfficialProviderSpec,
    config_env: dict[str, str],
) -> dict[str, object] | None:
    key_items = collect_provider_api_key_items(spec, config_env)
    if not key_items:
        return None
    return key_items[0]


def _provider_has_inline_api_key(provider: dict[str, object]) -> bool:
    api_key = str(provider.get("apiKey", "") or "").strip()
    if not api_key:
        return False
    return bool(resolve_api_key_config_value(api_key, {}))


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
        env_item = _official_provider_env_item(spec, config_env)
        env_key = str(env_item.get("value", "") or "").strip() if env_item else ""
        if not env_key or _provider_has_inline_api_key(provider):
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
        api_key = str(provider.get("apiKey", "") or "").strip()
        env_value = str(config_env.get(api_key, "") or "").strip()
        if not env_value:
            continue
        provider["apiKey"] = env_value
        consumed_env_names.add(api_key)
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
        if is_env_reference(api_key):
            names.add(api_key)
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
    if not isinstance(node, str) or not _path_likely_contains_model_ref(path_parts):
        return set()
    matched = _match_builtin_provider_spec(node)
    if matched is None:
        return set()
    spec, _model_name = matched
    return set(spec.exact_env_keys)


def _dotenv_env_names_for_payload(payload: dict[str, object]) -> set[str]:
    names: set[str] = set()
    models = payload.get("models")
    if isinstance(models, dict):
        providers = models.get("providers")
        if isinstance(providers, dict):
            names.update(_provider_env_names(providers))
    names.update(_builtin_model_env_names(payload))
    return {name for name in names if is_env_reference(name)}


def _iter_staged_dotenv_files(staging_root: Path) -> list[Path]:
    root = Path(staging_root)
    if not root.is_dir():
        return []
    result: list[Path] = []
    for file_path in root.rglob(".env"):
        if not file_path.is_file():
            continue
        try:
            rel_parts = file_path.relative_to(root).parts
        except ValueError:
            continue
        if rel_parts and rel_parts[0] in {"_scan_only", ".temp"}:
            continue
        result.append(file_path)
    return sorted(result, key=lambda item: item.as_posix())


def collect_openclaw_staged_dotenv_env(staging_root: Path, config_text: str) -> dict[str, str]:
    try:
        payload = json.loads(config_text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}

    names = _dotenv_env_names_for_payload(payload)
    if not names:
        return {}

    fields = UrlProxyFieldSet(api_key_fields=frozenset(names), base_url_fields=frozenset())
    result: dict[str, str] = {}
    root = Path(staging_root)
    for file_path in _iter_staged_dotenv_files(root):
        try:
            relpath = file_path.relative_to(root).as_posix()
        except ValueError:
            continue
        for candidate in scan_dotenv(file_path, relpath, fields=fields):
            if candidate.field not in result:
                value = real_value(candidate.value)
                if value:
                    result[candidate.field] = value
    return result


def _rewrite_builtin_model_refs(
    node: object,
    *,
    path_parts: tuple[str, ...],
    providers: dict[str, object],
    assigned_names: dict[str, str],
    model_template: dict[str, object] | None,
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

    if not isinstance(node, str) or not _path_likely_contains_model_ref(path_parts):
        return node, 0

    matched = _match_builtin_provider_spec(node)
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
    dotenv_env: dict[str, str] | None = None,
) -> tuple[str, int]:
    try:
        payload = json.loads(config_text)
    except json.JSONDecodeError:
        return config_text, 0
    if not isinstance(payload, dict):
        return config_text, 0

    model_template = _discover_model_template(payload)
    models = payload.get("models")
    if not isinstance(models, dict):
        models = {}
        payload["models"] = models
    providers = models.get("providers")
    if not isinstance(providers, dict):
        providers = {}
        models["providers"] = providers
    config_env = dict(dotenv_env or {})
    config_env.update(_openclaw_config_env(payload))

    assigned_names: dict[str, str] = {}
    rewritten_payload, rewrite_count = _rewrite_builtin_model_refs(
        payload,
        path_parts=(),
        providers=providers,
        assigned_names=assigned_names,
        model_template=model_template,
    )
    official_key_rewrites, consumed_env_names = _materialize_official_provider_env_keys(providers, config_env)
    provider_ref_rewrites, provider_ref_consumed_env_names = _materialize_provider_env_references(providers, config_env)
    consumed_env_names.update(provider_ref_consumed_env_names)
    provider_key_rewrites = official_key_rewrites + provider_ref_rewrites
    if provider_key_rewrites:
        rewritten_payload["models"] = clone_json_value(models)
        _drop_consumed_config_env(rewritten_payload, consumed_env_names)
    if rewrite_count <= 0:
        if provider_key_rewrites <= 0:
            return config_text, 0
        return json.dumps(rewritten_payload, ensure_ascii=False, indent=2) + "\n", provider_key_rewrites
    if not str(models.get("mode", "")).strip():
        models["mode"] = _DEFAULT_MODELS_MODE
    rewritten_payload["models"] = clone_json_value(models)
    return json.dumps(rewritten_payload, ensure_ascii=False, indent=2) + "\n", rewrite_count + provider_key_rewrites


__all__ = [
    "collect_openclaw_staged_dotenv_env",
    "rewrite_openclaw_builtin_models_as_explicit_providers",
]
