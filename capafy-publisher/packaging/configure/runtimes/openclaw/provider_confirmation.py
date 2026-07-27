from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from packaging._shared.reviewed_scan.query import reviewed_url_proxy_groups
from packaging.configure.runtimes.openclaw.official_providers import OPENCLAW_OFFICIAL_PROVIDER_NAMES_BY_MARKER
from packaging.configure.runtimes.openclaw.provider_scan import (
    OPENCLAW_CONFIG_REL,
    OPENCLAW_MAIN_MODELS_REL,
)
from packaging.configure.runtimes.openclaw.provider_usage import (
    builtin_openclaw_provider_map,
    get_openclaw_providers,
    model_id_from_openclaw_provider,
    provider_from_openclaw_model_ref,
)


_AUTH_PROFILE_GROUP_PREFIX = ".openclaw/agents/main/agent/auth-profiles.json#"
_CONFIG_PROVIDER_GROUP_PREFIX = ".openclaw/openclaw.json#models.providers."
_MAIN_MODELS_PROVIDER_GROUP_PREFIX = ".openclaw/agents/main/agent/models.json#providers."


def _provider_name_from_group(group: str) -> str:
    normalized = str(group or "").strip()
    if normalized.startswith(_CONFIG_PROVIDER_GROUP_PREFIX):
        return normalized[len(_CONFIG_PROVIDER_GROUP_PREFIX) :].split(".", 1)[0].strip()
    if normalized.startswith(_MAIN_MODELS_PROVIDER_GROUP_PREFIX):
        return normalized[len(_MAIN_MODELS_PROVIDER_GROUP_PREFIX) :].split(".", 1)[0].strip()
    return _official_provider_name_from_auth_profile_group(normalized)


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
        provider_name = OPENCLAW_OFFICIAL_PROVIDER_NAMES_BY_MARKER.get(token)
        if provider_name:
            return provider_name
    return ""


def _confirmed_openclaw_provider_fields(
    reviewed_scan: dict[str, Any],
) -> dict[str, dict[str, str]]:
    fields: dict[str, dict[str, str]] = {"model": {}, "api_format": {}}
    url_proxy = reviewed_scan.get("url_proxy", [])
    if not isinstance(url_proxy, list):
        return fields
    for entry in url_proxy:
        if not isinstance(entry, dict):
            continue
        provider = _provider_name_from_group(str(entry.get("url_proxy_group", "") or ""))
        if not provider:
            continue
        model = str(entry.get("model", "") or "").strip()
        if model:
            fields["model"][provider] = model
        api_format = str(entry.get("api_format", "") or "").strip()
        if api_format:
            fields["api_format"][provider] = api_format
    return fields


def _allowed_openclaw_provider_names(reviewed_scan: dict[str, Any]) -> set[str]:
    return {
        provider
        for provider in (
            _provider_name_from_group(group)
            for group in reviewed_url_proxy_groups(reviewed_scan)
        )
        if provider
    }


def _filter_model_ref_list(
    values: object,
    *,
    allowed: set[str],
    managed_providers: set[str],
) -> tuple[object, int]:
    if not isinstance(values, list):
        return values, 0
    filtered = [
        value
        for value in values
        if not isinstance(value, str)
        or provider_from_openclaw_model_ref(value) not in managed_providers
        or provider_from_openclaw_model_ref(value) in allowed
    ]
    return filtered, 1 if filtered != values else 0


def _rewrite_openclaw_model_defaults(
    payload: dict[str, Any],
    *,
    allowed: set[str],
    fallback_ref: str,
    managed_providers: set[str],
    replacement_refs: Optional[dict[str, str]] = None,
    builtin_provider_map: Optional[dict[str, str]] = None,
) -> int:
    replacement_refs = replacement_refs or {}
    builtin_provider_map = builtin_provider_map or {}
    rewrites = 0
    agents = payload.get("agents")
    if not isinstance(agents, dict):
        return 0

    def rewrite_managed_model_ref(value: object) -> tuple[object, int]:
        if not isinstance(value, str):
            return value, 0
        provider = provider_from_openclaw_model_ref(value)
        if provider in managed_providers:
            if provider not in allowed:
                return fallback_ref, 1
            replacement_provider = provider
        elif provider in builtin_provider_map:
            replacement_provider = builtin_provider_map[provider]
        else:
            return value, 0
        replacement_ref = replacement_refs.get(replacement_provider, "")
        if not replacement_ref or value == replacement_ref:
            return value, 0
        return replacement_ref, 1

    def rewrite_managed_model_ref_list(values: object) -> tuple[object, int]:
        if not isinstance(values, list):
            return values, 0
        updated = [
            rewrite_managed_model_ref(value)[0] if isinstance(value, str) else value
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
                node["primary"], count = rewrite_managed_model_ref(node.get("primary"))
                rewrites += count
            if "fallbacks" in node:
                node["fallbacks"], count = _filter_model_ref_list(
                    node.get("fallbacks"),
                    allowed=allowed,
                    managed_providers=managed_providers,
                )
                rewrites += count
                node["fallbacks"], count = rewrite_managed_model_ref_list(node.get("fallbacks"))
                rewrites += count
        models = defaults.get("models")
        if isinstance(models, dict):
            renamed: dict[str, Any] = {}
            for model_ref in list(models):
                provider = provider_from_openclaw_model_ref(model_ref)
                if provider in builtin_provider_map or (
                    provider in managed_providers and provider not in allowed
                ):
                    models.pop(model_ref, None)
                    rewrites += 1
                    continue
                if provider in managed_providers and provider in allowed:
                    replacement_ref = replacement_refs.get(provider, "")
                    if replacement_ref and replacement_ref != model_ref:
                        renamed[replacement_ref] = models.pop(model_ref)
                        rewrites += 1
            models.update(renamed)

    agent_list = agents.get("list")
    if isinstance(agent_list, list):
        for agent in agent_list:
            if not isinstance(agent, dict) or "model" not in agent:
                continue
            agent["model"], count = rewrite_managed_model_ref(agent.get("model"))
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
        models = provider.get("models")
        if not isinstance(models, list):
            continue
        for model in models:
            if not isinstance(model, dict) or "api" not in model:
                continue
            if model.get("api") != api_format:
                model["api"] = api_format
                rewrites += 1
    return rewrites


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _main_models_providers(payload: dict[str, Any]) -> dict[str, Any]:
    providers = payload.get("providers")
    return providers if isinstance(providers, dict) else {}


def _ordered_provider_names(*provider_maps: dict[str, Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for providers in provider_maps:
        for provider_name, provider in providers.items():
            normalized = str(provider_name)
            if normalized in seen or not isinstance(provider, dict):
                continue
            seen.add(normalized)
            result.append(normalized)
    return result


def _provider_payload(
    provider_name: str,
    *provider_maps: dict[str, Any],
) -> Optional[dict[str, Any]]:
    for providers in provider_maps:
        provider = providers.get(provider_name)
        if isinstance(provider, dict):
            return provider
    return None


def _prune_unconfirmed_providers(
    providers: dict[str, Any],
    *,
    allowed: set[str],
) -> int:
    removed = 0
    for provider_name in list(providers):
        if str(provider_name) in allowed:
            continue
        providers.pop(provider_name, None)
        removed += 1
    return removed


def rewrite_openclaw_confirmed_providers(
    staging_root: Path,
    reviewed_scan: dict[str, Any],
) -> dict[str, Any]:
    allowed = _allowed_openclaw_provider_names(reviewed_scan)
    if not allowed:
        return {"openclaw_confirmed_provider_rewrites": 0}
    config_path = staging_root / OPENCLAW_CONFIG_REL
    if not config_path.is_file():
        return {"openclaw_confirmed_provider_rewrites": 0}
    payload = _load_json_object(config_path)
    if not payload:
        return {"openclaw_confirmed_provider_rewrites": 0}

    models_path = staging_root / OPENCLAW_MAIN_MODELS_REL
    main_models_payload = _load_json_object(models_path)
    providers = get_openclaw_providers(payload)
    main_models_providers = _main_models_providers(main_models_payload)
    provider_maps = (providers, main_models_providers)

    ordered_allowed = [
        provider_name
        for provider_name in _ordered_provider_names(*provider_maps)
        if provider_name in allowed
    ]
    if not ordered_allowed:
        return {"openclaw_confirmed_provider_rewrites": 0}
    fallback_provider = ordered_allowed[0]

    original_payload = json.loads(json.dumps(payload, ensure_ascii=False))
    original_main_models_payload = json.loads(json.dumps(main_models_payload, ensure_ascii=False))
    managed_providers = set(_ordered_provider_names(*provider_maps))
    allowed_provider_names = set(ordered_allowed)
    removed = sum(
        _prune_unconfirmed_providers(provider_map, allowed=allowed_provider_names)
        for provider_map in provider_maps
    )

    confirmed_fields = _confirmed_openclaw_provider_fields(reviewed_scan)
    confirmed_models = confirmed_fields["model"]
    confirmed_api_formats = confirmed_fields["api_format"]
    api_format_rewrites = sum(
        _rewrite_confirmed_provider_api_formats(provider_map, confirmed_api_formats)
        for provider_map in provider_maps
    )
    replacement_refs: dict[str, str] = {}
    model_rewrites = 0
    for provider_map in provider_maps:
        provider_replacement_refs, provider_model_rewrites = _rewrite_confirmed_provider_models(
            provider_map,
            confirmed_models,
        )
        replacement_refs.update(provider_replacement_refs)
        model_rewrites += provider_model_rewrites
    fallback_payload = _provider_payload(fallback_provider, *provider_maps) or {}
    fallback_model_id = model_id_from_openclaw_provider(fallback_payload)
    fallback_ref = replacement_refs.get(fallback_provider) or (
        f"{fallback_provider}/{fallback_model_id}" if fallback_model_id else fallback_provider
    )
    builtin_provider_map = builtin_openclaw_provider_map(allowed_provider_names)
    rewrites = _rewrite_openclaw_model_defaults(
        payload,
        allowed=allowed_provider_names,
        fallback_ref=fallback_ref,
        managed_providers=managed_providers,
        replacement_refs=replacement_refs,
        builtin_provider_map=builtin_provider_map,
    )
    if payload != original_payload:
        config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if main_models_payload != original_main_models_payload:
        models_path.write_text(
            json.dumps(main_models_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    changed = payload != original_payload or main_models_payload != original_main_models_payload
    return {
        "openclaw_confirmed_provider_rewrites": removed + rewrites + model_rewrites + api_format_rewrites,
        "openclaw_confirmed_provider_selected": fallback_provider if changed else "",
        "openclaw_confirmed_provider_removed": removed,
        "openclaw_confirmed_model_rewrites": model_rewrites,
        "openclaw_confirmed_api_format_rewrites": api_format_rewrites,
    }


__all__ = ["rewrite_openclaw_confirmed_providers"]
