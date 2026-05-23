from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packaging._shared.openclaw.official_providers import OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME
from packaging._shared.reviewed_scan.query import reviewed_url_proxy_groups as _reviewed_url_proxy_groups


_OFFICIAL_AUTH_PROFILE_PROVIDER_NAMES = {
    "anthropic": "publisher_anthropic_official",
    "claude": "publisher_anthropic_official",
    "gemini": "publisher_google_official",
    "google": "publisher_google_official",
    "openai": "publisher_openai_official",
}
_OFFICIAL_PLUGIN_PROVIDER_NAMES = {
    "anthropic": "publisher_anthropic_official",
    "claude": "publisher_anthropic_official",
    "gemini": "publisher_google_official",
    "google": "publisher_google_official",
    "openai": "publisher_openai_official",
}
_AUTH_PROFILE_GROUP_PREFIX = ".openclaw/agents/main/agent/auth-profiles.json#"


def _allowed_openclaw_provider_names(reviewed_scan: dict[str, Any]) -> set[str]:
    prefix = ".openclaw/openclaw.json#models.providers."
    providers: set[str] = set()
    for group in _reviewed_url_proxy_groups(reviewed_scan):
        if not group.startswith(prefix):
            auth_profile_provider = _official_provider_name_from_auth_profile_group(group)
            if auth_profile_provider:
                providers.add(auth_profile_provider)
            continue
        provider = group[len(prefix) :].split(".", 1)[0].strip()
        if provider:
            providers.add(provider)
    return providers


def _confirmed_model_by_openclaw_provider(reviewed_scan: dict[str, Any]) -> dict[str, str]:
    prefix = ".openclaw/openclaw.json#models.providers."
    models: dict[str, str] = {}
    url_proxy = reviewed_scan.get("url_proxy", [])
    if not isinstance(url_proxy, list):
        return models
    for entry in url_proxy:
        if not isinstance(entry, dict):
            continue
        group = str(entry.get("url_proxy_group", "") or "").strip()
        provider = ""
        if group.startswith(prefix):
            provider = group[len(prefix) :].split(".", 1)[0].strip()
        else:
            provider = _official_provider_name_from_auth_profile_group(group)
        model = str(entry.get("model", "") or "").strip()
        if provider and model:
            models[provider] = model
    return models


def _confirmed_api_format_by_openclaw_provider(reviewed_scan: dict[str, Any]) -> dict[str, str]:
    prefix = ".openclaw/openclaw.json#models.providers."
    formats: dict[str, str] = {}
    url_proxy = reviewed_scan.get("url_proxy", [])
    if not isinstance(url_proxy, list):
        return formats
    for entry in url_proxy:
        if not isinstance(entry, dict):
            continue
        group = str(entry.get("url_proxy_group", "") or "").strip()
        provider = ""
        if group.startswith(prefix):
            provider = group[len(prefix) :].split(".", 1)[0].strip()
        else:
            provider = _official_provider_name_from_auth_profile_group(group)
        api_format = str(entry.get("api_format", "") or "").strip()
        if provider and api_format:
            formats[provider] = api_format
    return formats


def _official_provider_name_from_auth_profile_group(group: str) -> str:
    if not group.startswith(_AUTH_PROFILE_GROUP_PREFIX):
        return ""
    suffix = group[len(_AUTH_PROFILE_GROUP_PREFIX) :].strip().lower()
    if not suffix:
        return ""
    path_tokens = [
        token
        for token in suffix.replace("[", ".").replace("]", ".").replace("/", ".").split(".")
        if token
    ]
    for token in reversed(path_tokens):
        provider_name = _OFFICIAL_AUTH_PROFILE_PROVIDER_NAMES.get(token)
        if provider_name:
            return provider_name
    return ""


def _provider_from_model_ref(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().split("/", 1)[0]


def _confirmed_builtin_provider_map(allowed: set[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for provider_name in allowed:
        spec = OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME.get(provider_name)
        if spec is None:
            continue
        for prefix in spec.model_prefixes:
            builtin_provider = prefix.rstrip("/")
            if builtin_provider:
                result[builtin_provider] = provider_name
        for marker in spec.markers:
            if marker:
                result[marker] = provider_name
    return result


def _model_id_from_entry(entry: object) -> str:
    if isinstance(entry, dict):
        for key in ("id", "name", "model"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(entry, str):
        return entry.strip()
    return ""


def _first_model_ref(provider_name: str, provider_payload: dict[str, Any]) -> str:
    models = provider_payload.get("models")
    if isinstance(models, list):
        for entry in models:
            model_id = _model_id_from_entry(entry)
            if model_id:
                return f"{provider_name}/{model_id}"
    return provider_name


def _rewrite_model_ref(value: object, *, allowed: set[str], fallback_ref: str) -> tuple[object, int]:
    provider = _provider_from_model_ref(value)
    if not provider or provider in allowed:
        return value, 0
    return fallback_ref, 1


def _filter_model_ref_list(values: object, *, allowed: set[str]) -> tuple[object, int]:
    if not isinstance(values, list):
        return values, 0
    filtered = [value for value in values if not isinstance(value, str) or _provider_from_model_ref(value) in allowed]
    return filtered, 1 if filtered != values else 0


def _rewrite_openclaw_model_defaults(
    payload: dict[str, Any],
    *,
    allowed: set[str],
    fallback_ref: str,
    replacement_refs: dict[str, str] | None = None,
    builtin_provider_map: dict[str, str] | None = None,
) -> int:
    replacement_refs = replacement_refs or {}
    builtin_provider_map = builtin_provider_map or {}
    rewrites = 0
    agents = payload.get("agents")
    if not isinstance(agents, dict):
        return 0

    def rewrite_allowed_model_ref(value: object) -> tuple[object, int]:
        if not isinstance(value, str):
            return value, 0
        provider = _provider_from_model_ref(value)
        replacement_provider = builtin_provider_map.get(provider, provider)
        replacement_ref = replacement_refs.get(replacement_provider, "")
        if not replacement_ref or value == replacement_ref:
            return value, 0
        return replacement_ref, 1

    def rewrite_allowed_model_ref_list(values: object) -> tuple[object, int]:
        if not isinstance(values, list):
            return values, 0
        updated = [
            rewrite_allowed_model_ref(value)[0] if isinstance(value, str) else value
            for value in values
        ]
        return updated, 1 if updated != values else 0

    defaults = agents.get("defaults")
    if isinstance(defaults, dict):
        for key in ("model", "imageModel"):
            node = defaults.get(key)
            if not isinstance(node, dict):
                continue
            if "primary" in node:
                node["primary"], count = _rewrite_model_ref(node.get("primary"), allowed=allowed, fallback_ref=fallback_ref)
                rewrites += count
                node["primary"], count = rewrite_allowed_model_ref(node.get("primary"))
                rewrites += count
            if "fallbacks" in node:
                node["fallbacks"], count = _filter_model_ref_list(node.get("fallbacks"), allowed=allowed)
                rewrites += count
                node["fallbacks"], count = rewrite_allowed_model_ref_list(node.get("fallbacks"))
                rewrites += count
        models = defaults.get("models")
        if isinstance(models, dict):
            for model_ref in list(models):
                provider = _provider_from_model_ref(model_ref)
                if provider in builtin_provider_map or provider not in allowed:
                    models.pop(model_ref, None)
                    rewrites += 1

    agent_list = agents.get("list")
    if isinstance(agent_list, list):
        for agent in agent_list:
            if not isinstance(agent, dict) or "model" not in agent:
                continue
            agent["model"], count = _rewrite_model_ref(agent.get("model"), allowed=allowed, fallback_ref=fallback_ref)
            rewrites += count
            agent["model"], count = rewrite_allowed_model_ref(agent.get("model"))
            rewrites += count
    return rewrites


def _rewrite_confirmed_provider_models(
    providers: dict[str, Any],
    confirmed_models: dict[str, str],
) -> tuple[dict[str, str], int]:
    replacement_refs: dict[str, str] = {}
    rewrites = 0
    for provider_name, model_id in confirmed_models.items():
        provider = providers.get(provider_name)
        if not isinstance(provider, dict) or not model_id:
            continue
        models = provider.get("models")
        if not isinstance(models, list) or not models:
            provider["models"] = [{"id": model_id, "name": model_id}]
            rewrites += 1
            replacement_refs[provider_name] = f"{provider_name}/{model_id}"
            continue
        first_model = models[0]
        if isinstance(first_model, dict):
            if first_model.get("id") != model_id:
                first_model["id"] = model_id
                rewrites += 1
            if first_model.get("name") != model_id:
                first_model["name"] = model_id
                rewrites += 1
        else:
            models[0] = {"id": model_id, "name": model_id}
            rewrites += 1
        replacement_refs[provider_name] = f"{provider_name}/{model_id}"
    return replacement_refs, rewrites


def _prune_confirmed_official_plugin_entries(payload: dict[str, Any], *, allowed: set[str]) -> int:
    allowed_plugin_names = {
        plugin_name
        for plugin_name, provider_name in _OFFICIAL_PLUGIN_PROVIDER_NAMES.items()
        if provider_name in allowed
    }
    if not allowed_plugin_names:
        return 0
    plugins = payload.get("plugins")
    if not isinstance(plugins, dict):
        return 0
    entries = plugins.get("entries")
    if not isinstance(entries, dict):
        return 0
    rewrites = 0
    for plugin_name in list(entries):
        if str(plugin_name).strip().lower() in allowed_plugin_names:
            entries.pop(plugin_name, None)
            rewrites += 1
    return rewrites


def _rewrite_confirmed_provider_api_formats(
    providers: dict[str, Any],
    confirmed_api_formats: dict[str, str],
) -> int:
    rewrites = 0
    for provider_name, api_format in confirmed_api_formats.items():
        provider = providers.get(provider_name)
        if not isinstance(provider, dict) or not api_format:
            continue
        if provider.get("api") != api_format:
            provider["api"] = api_format
            rewrites += 1
    return rewrites


def rewrite_openclaw_confirmed_providers(
    staging_root: Path,
    reviewed_scan: dict[str, Any],
) -> dict[str, Any]:
    allowed = _allowed_openclaw_provider_names(reviewed_scan)
    if not allowed:
        return {"openclaw_confirmed_provider_rewrites": 0}
    config_path = staging_root / ".openclaw" / "openclaw.json"
    if not config_path.is_file():
        return {"openclaw_confirmed_provider_rewrites": 0}
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"openclaw_confirmed_provider_rewrites": 0}
    if not isinstance(payload, dict):
        return {"openclaw_confirmed_provider_rewrites": 0}

    models = payload.get("models")
    if not isinstance(models, dict):
        return {"openclaw_confirmed_provider_rewrites": 0}
    providers = models.get("providers")
    if not isinstance(providers, dict):
        return {"openclaw_confirmed_provider_rewrites": 0}

    ordered_allowed = [
        str(provider_name)
        for provider_name in providers
        if str(provider_name) in allowed and isinstance(providers.get(provider_name), dict)
    ]
    if not ordered_allowed:
        return {"openclaw_confirmed_provider_rewrites": 0}
    fallback_provider = ordered_allowed[0]

    original_payload = json.loads(json.dumps(payload, ensure_ascii=False))
    removed = 0
    for provider_name in list(providers):
        if str(provider_name) in allowed:
            continue
        providers.pop(provider_name, None)
        removed += 1

    confirmed_api_formats = _confirmed_api_format_by_openclaw_provider(reviewed_scan)
    api_format_rewrites = _rewrite_confirmed_provider_api_formats(providers, confirmed_api_formats)
    confirmed_models = _confirmed_model_by_openclaw_provider(reviewed_scan)
    replacement_refs, model_rewrites = _rewrite_confirmed_provider_models(providers, confirmed_models)
    fallback_ref = replacement_refs.get(fallback_provider) or _first_model_ref(fallback_provider, providers[fallback_provider])
    builtin_provider_map = _confirmed_builtin_provider_map(set(ordered_allowed))
    rewrites = _rewrite_openclaw_model_defaults(
        payload,
        allowed=set(ordered_allowed),
        fallback_ref=fallback_ref,
        replacement_refs=replacement_refs,
        builtin_provider_map=builtin_provider_map,
    )
    plugin_rewrites = _prune_confirmed_official_plugin_entries(payload, allowed=set(ordered_allowed))
    if payload != original_payload:
        config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "openclaw_confirmed_provider_rewrites": removed + rewrites + model_rewrites + api_format_rewrites + plugin_rewrites,
        "openclaw_confirmed_provider_selected": fallback_provider if payload != original_payload else "",
        "openclaw_confirmed_provider_removed": removed,
        "openclaw_confirmed_model_rewrites": model_rewrites,
        "openclaw_confirmed_api_format_rewrites": api_format_rewrites,
        "openclaw_confirmed_plugin_rewrites": plugin_rewrites,
    }


__all__ = ["rewrite_openclaw_confirmed_providers"]
