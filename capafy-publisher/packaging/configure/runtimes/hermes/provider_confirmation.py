from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from packaging._shared.config_files.yaml_loader import (
    get_yaml_path_value,
    remove_yaml_object_key_at_path,
    safe_yaml_dumps,
    safe_yaml_mapping_loads,
    set_yaml_path_value,
)
from packaging._shared.llm.official_providers import find_official_provider_by_marker
from packaging.configure.runtimes.hermes.api_modes import hermes_api_mode_for_config


CONFIG_REL = ".hermes/config.yaml"
_CUSTOM_PROVIDER_PREFIX = "custom_providers["


def rewrite_hermes_confirmed_providers(
    staging_root: Path,
    reviewed_scan: dict[str, Any],
) -> dict[str, Any]:
    entries = _confirmed_entries(reviewed_scan)
    if entries is None:
        return {"hermes_confirmed_provider_rewrites": 0}
    config_path = Path(staging_root) / CONFIG_REL
    if not config_path.is_file():
        return {"hermes_confirmed_provider_rewrites": 0}
    try:
        payload = safe_yaml_mapping_loads(config_path.read_text(encoding="utf-8"))
    except (OSError, RuntimeError, ValueError):
        return {"hermes_confirmed_provider_rewrites": 0}

    rewrites = 0
    allowed_custom_names = _confirmed_custom_provider_names(payload, entries)
    for group_path, entry in entries.items():
        key_path = _group_key_path(group_path)
        if not key_path:
            continue
        rewrites += int(set_yaml_path_value(payload, (*key_path, "api_key"), _side_placeholder(entry, "api_key")))
        rewrites += int(set_yaml_path_value(payload, (*key_path, "base_url"), _side_placeholder(entry, "url")))
        model = str(entry.get("model", "") or "").strip()
        if model:
            model_field = "default" if group_path == "model" else "model"
            rewrites += int(set_yaml_path_value(payload, (*key_path, model_field), model))
        api_format = str(entry.get("api_format", "") or "").strip()
        if api_format:
            rewrites += int(set_yaml_path_value(
                payload,
                (*key_path, "api_mode"),
                hermes_api_mode_for_config(api_format),
            ))
            existing = get_yaml_path_value(payload, (*key_path, "api_format"))
            if existing is not None:
                rewrites += int(remove_yaml_object_key_at_path(payload, (*key_path, "api_format")))

    pruned, removed = _prune_unconfirmed_custom_providers(payload, allowed_custom_names)
    rewrites += pruned
    rewrites += _sync_custom_provider_reference_models(payload)

    if rewrites:
        config_path.write_text(safe_yaml_dumps(payload), encoding="utf-8")
    return {
        "hermes_confirmed_provider_rewrites": rewrites,
        "hermes_confirmed_provider_removed": removed,
    }


def _confirmed_entries(reviewed_scan: dict[str, Any]) -> Optional[dict[str, dict[str, Any]]]:
    if "url_proxy" not in reviewed_scan:
        return None
    entries = reviewed_scan.get("url_proxy", [])
    if not isinstance(entries, list):
        return None
    result: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        group = str(entry.get("url_proxy_group", "") or "").strip()
        prefix = f"{CONFIG_REL}#"
        if not group.startswith(prefix):
            continue
        group_path = group[len(prefix) :]
        if not group_path:
            continue
        result[group_path] = entry
    return result


def _side_placeholder(entry: dict[str, Any], side_name: str) -> str:
    side = entry.get(side_name)
    if not isinstance(side, dict):
        return ""
    return str(side.get("placeholder", "") or "").strip()


def _group_key_path(group_path: str) -> tuple[str, ...]:
    normalized = str(group_path or "").strip()
    if not normalized:
        return ()
    if normalized == "model":
        return ("model",)
    if normalized.startswith("auxiliary."):
        suffix = normalized[len("auxiliary.") :].strip()
        return ("auxiliary", suffix) if suffix else ()
    if normalized == "delegation":
        return ("delegation",)
    if normalized.startswith("fallback_providers["):
        return (normalized,)
    if normalized.startswith("custom_providers["):
        return (normalized,)
    return ()


def _custom_provider_index(group_path: str) -> Optional[int]:
    normalized = str(group_path or "").strip()
    if not normalized.startswith(_CUSTOM_PROVIDER_PREFIX):
        return None
    suffix = normalized[len(_CUSTOM_PROVIDER_PREFIX) :]
    raw_index = suffix.split("]", 1)[0]
    try:
        return int(raw_index)
    except ValueError:
        return None


def _custom_provider_name(provider: object) -> str:
    if not isinstance(provider, dict):
        return ""
    return str(provider.get("name", "") or "").strip()


def _confirmed_custom_provider_names(
    payload: dict[str, Any],
    entries: dict[str, dict[str, Any]],
) -> set[str]:
    providers = payload.get("custom_providers")
    if not isinstance(providers, list):
        return set()
    result: set[str] = set()
    for group_path in entries:
        index = _custom_provider_index(group_path)
        if index is None or index < 0 or index >= len(providers):
            continue
        name = _custom_provider_name(providers[index])
        if name:
            result.add(name)
    return result


def _custom_reference_name(value: object, custom_names: set[str]) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    lowered = normalized.lower()
    if lowered.startswith("custom:"):
        return normalized.split(":", 1)[1].strip()
    if lowered == "openrouter" or find_official_provider_by_marker(lowered) is not None:
        return ""
    return normalized if normalized in custom_names else ""


def _set_replacement_reference(
    block: dict[str, Any],
    *,
    replacement_name: str,
    replacement_model: str,
    model_field: str,
) -> int:
    replacement = f"custom:{replacement_name}"
    rewrites = 0
    if block.get("provider") != replacement:
        block["provider"] = replacement
        rewrites += 1
    if replacement_model and block.get(model_field) != replacement_model:
        block[model_field] = replacement_model
        rewrites += 1
    return rewrites


def _filter_fallback_providers(
    payload: dict[str, Any],
    *,
    allowed_names: set[str],
    custom_names: set[str],
) -> int:
    fallback = payload.get("fallback_providers")
    if not isinstance(fallback, list):
        return 0
    filtered = []
    for item in fallback:
        if not isinstance(item, dict):
            filtered.append(item)
            continue
        ref_name = _custom_reference_name(item.get("provider"), custom_names)
        if ref_name and ref_name not in allowed_names:
            continue
        filtered.append(item)
    if filtered == fallback:
        return 0
    if filtered:
        payload["fallback_providers"] = filtered
    else:
        payload.pop("fallback_providers", None)
    return 1


def _provider_model_by_name(payload: dict[str, Any]) -> dict[str, str]:
    providers = payload.get("custom_providers")
    if not isinstance(providers, list):
        return {}
    result: dict[str, str] = {}
    for provider in providers:
        name = _custom_provider_name(provider)
        if not name or not isinstance(provider, dict):
            continue
        model = str(provider.get("model", "") or "").strip()
        if model:
            result[name] = model
    return result


def _sync_custom_provider_reference_models(payload: dict[str, Any]) -> int:
    model_by_name = _provider_model_by_name(payload)
    if not model_by_name:
        return 0
    custom_names = set(model_by_name)
    rewrites = 0

    block = payload.get("model")
    if isinstance(block, dict):
        rewrites += _sync_custom_provider_reference_model(
            block,
            custom_names=custom_names,
            model_by_name=model_by_name,
            model_field="default",
        )

    return rewrites


def _sync_custom_provider_reference_model(
    block: dict[str, Any],
    *,
    custom_names: set[str],
    model_by_name: dict[str, str],
    model_field: str,
) -> int:
    ref_name = _custom_reference_name(block.get("provider"), custom_names)
    model = model_by_name.get(ref_name, "")
    if not model or block.get(model_field) == model:
        return 0
    block[model_field] = model
    return 1


def _custom_provider_names(payload: dict[str, Any]) -> set[str]:
    providers = payload.get("custom_providers")
    if not isinstance(providers, list):
        return set()
    return {
        name
        for name in (_custom_provider_name(provider) for provider in providers)
        if name
    }


def _first_allowed_custom_provider_name(payload: dict[str, Any], allowed_names: set[str]) -> str:
    providers = payload.get("custom_providers")
    if not isinstance(providers, list):
        return ""
    for provider in providers:
        name = _custom_provider_name(provider)
        if name in allowed_names:
            return name
    return ""


def _prune_unconfirmed_custom_providers(payload: dict[str, Any], allowed_names: set[str]) -> tuple[int, int]:
    providers = payload.get("custom_providers")
    if not isinstance(providers, list):
        return 0, 0
    original_custom_names = _custom_provider_names(payload)
    filtered: list[object] = []
    removed = 0
    for provider in providers:
        name = _custom_provider_name(provider)
        if not name or name not in allowed_names:
            removed += 1
            continue
        filtered.append(provider)
    rewrites = 0
    if removed:
        if filtered:
            payload["custom_providers"] = filtered
        else:
            payload.pop("custom_providers", None)
        rewrites += 1
        rewrites += _repair_custom_provider_references_for_names(
            payload,
            allowed_names=allowed_names,
            custom_names=original_custom_names,
        )
    return rewrites, removed


def _repair_custom_provider_references_for_names(
    payload: dict[str, Any],
    *,
    allowed_names: set[str],
    custom_names: set[str],
) -> int:
    replacement_name = _first_allowed_custom_provider_name(payload, allowed_names)
    replacement_model = _provider_model_by_name(payload).get(replacement_name, "")
    rewrites = 0
    for key in ("model", "delegation"):
        block = payload.get(key)
        if not isinstance(block, dict):
            continue
        ref_name = _custom_reference_name(block.get("provider"), custom_names)
        if not ref_name or ref_name in allowed_names:
            continue
        if replacement_name:
            rewrites += _set_replacement_reference(
                block,
                replacement_name=replacement_name,
                replacement_model=replacement_model,
                model_field="default" if key == "model" else "model",
            )
        else:
            payload.pop(key, None)
            rewrites += 1

    auxiliary = payload.get("auxiliary")
    if isinstance(auxiliary, dict):
        for name in list(auxiliary):
            block = auxiliary.get(name)
            if not isinstance(block, dict):
                continue
            ref_name = _custom_reference_name(block.get("provider"), custom_names)
            if not ref_name or ref_name in allowed_names:
                continue
            if replacement_name:
                rewrites += _set_replacement_reference(
                    block,
                    replacement_name=replacement_name,
                    replacement_model=replacement_model,
                    model_field="model",
                )
            else:
                auxiliary.pop(name, None)
                rewrites += 1
        if not auxiliary:
            payload.pop("auxiliary", None)
            rewrites += 1

    rewrites += _filter_fallback_providers(payload, allowed_names=allowed_names, custom_names=custom_names)
    rewrites += _filter_credential_pool_strategies(payload, allowed_names=allowed_names, custom_names=custom_names)
    return rewrites


def _filter_credential_pool_strategies(
    payload: dict[str, Any],
    *,
    allowed_names: set[str],
    custom_names: set[str],
) -> int:
    strategies = payload.get("credential_pool_strategies")
    if not isinstance(strategies, dict):
        return 0
    rewrites = 0
    for key in list(strategies):
        ref_name = _custom_reference_name(key, custom_names)
        if ref_name and ref_name not in allowed_names:
            strategies.pop(key, None)
            rewrites += 1
    if not strategies:
        payload.pop("credential_pool_strategies", None)
        rewrites += 1
    return rewrites


__all__ = ["rewrite_hermes_confirmed_providers"]
