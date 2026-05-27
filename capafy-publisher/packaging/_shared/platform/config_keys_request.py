from __future__ import annotations

import json
from pathlib import PurePosixPath
from typing import Any

from packaging._shared.contracts.reviewed_scan import (
    project_env_var_credentials_item,
    sanitize_reviewed_scan_payload,
)
from packaging.configure.scan.scan_only_paths import is_scan_only_source_path


_ENV_CONFIG_SETTINGS_BASENAMES = frozenset(
    {
        "managed-settings.json",
        "settings.json",
        "settings.local.json",
    }
)


def _strip_tracking_source(item: dict, *, label: str) -> str:
    raw_source = item.get("source")
    if not isinstance(raw_source, str):
        raise ValueError(f"{label}.source must be a string")
    source = raw_source.strip()
    if not source:
        raise ValueError(f"{label}.source must not be empty")
    return source


def _require_reviewed_use(entry: dict, *, label: str) -> str:
    raw_use = entry.get("use")
    if not isinstance(raw_use, str):
        raise ValueError(f"{label}.use must be a string")
    use = raw_use.strip()
    if not use:
        raise ValueError(f"{label}.use must not be empty for reviewed_scan")
    return use


def _strip_tracking_url_proxy_entry(entry: dict, *, index: int) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise ValueError("reviewed_scan_payload.url_proxy items must be objects")
    api_key = entry.get("api_key")
    url = entry.get("url")
    if not isinstance(api_key, dict):
        raise ValueError(f"reviewed_scan_payload.url_proxy[{index}].api_key must be an object")
    if not isinstance(url, dict):
        raise ValueError(f"reviewed_scan_payload.url_proxy[{index}].url must be an object")
    projected: dict[str, Any] = {
        "api_key": {
            "value": api_key.get("value", ""),
            "placeholder": api_key.get("placeholder", ""),
            "field": api_key.get("field", ""),
            "source": _strip_tracking_source(api_key, label=f"reviewed_scan_payload.url_proxy[{index}].api_key"),
        },
        "url": {
            "value": url.get("value", ""),
            "placeholder": url.get("placeholder", ""),
            "field": url.get("field", ""),
            "source": _strip_tracking_source(url, label=f"reviewed_scan_payload.url_proxy[{index}].url"),
        },
        "use": _require_reviewed_use(entry, label=f"reviewed_scan_payload.url_proxy[{index}]"),
    }
    model = str(entry.get("model", "") or "").strip()
    if model:
        projected["model"] = model
    api_format = str(entry.get("api_format", "") or "").strip()
    if not api_format:
        raise ValueError(f"reviewed_scan_payload.url_proxy[{index}].api_format must not be empty")
    projected["api_format"] = api_format
    value_type = str(url.get("value_type", "")).strip()
    if value_type:
        projected["url"]["value_type"] = value_type
    return projected


def _strip_tracking_generic_entry(entry: dict, *, index: int) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise ValueError("reviewed_scan_payload.generic items must be objects")
    source = _strip_tracking_source(entry, label=f"reviewed_scan_payload.generic[{index}]")
    projected = {
        "value": entry.get("value", ""),
        "placeholder": entry.get("placeholder", ""),
        "field": entry.get("field", ""),
        "source": source,
        "use": _require_reviewed_use(entry, label=f"reviewed_scan_payload.generic[{index}]"),
    }
    value_type = str(entry.get("value_type", "")).strip()
    if value_type:
        projected["value_type"] = value_type
    source_detail = str(entry.get("source_detail", "") or "").strip()
    if source_detail:
        projected["source_detail"] = source_detail
    occurrence_index = entry.get("occurrence_index")
    if occurrence_index not in (None, ""):
        projected["occurrence_index"] = occurrence_index
    return projected


def _is_uploadable_generic_entry(entry: Any) -> bool:
    return isinstance(entry, dict) and not is_scan_only_source_path(str(entry.get("source", "") or ""))


def _strip_tracking_env_var_entry(entry: dict, *, index: int) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise ValueError("reviewed_scan_payload.env_var items must be objects")
    return project_env_var_credentials_item(entry, label=f"reviewed_scan_payload.env_var[{index}]")


def _normalized_source_path(source: object) -> str:
    normalized = str(source or "").strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _is_dotenv_source(source: str) -> bool:
    path_name = PurePosixPath(source).name.lower()
    return path_name == ".env" or path_name.startswith(".env.")


def _is_settings_env_source(source: str) -> bool:
    return PurePosixPath(source).name.lower() in _ENV_CONFIG_SETTINGS_BASENAMES


def _env_config_field(entry: dict) -> str:
    field = str(entry.get("field", "") or "").strip()
    if field:
        return field
    source_detail = str(entry.get("source_detail", "") or "")
    for marker in ("env.", "/env/"):
        if marker not in source_detail:
            continue
        candidate = source_detail.rsplit(marker, 1)[-1].strip().strip("/")
        if candidate:
            return candidate
    return ""


def _referenced_in(entry: dict) -> tuple[str, ...]:
    raw_references = entry.get("referenced_in")
    if not isinstance(raw_references, list):
        return ()
    references: list[str] = []
    for raw_reference in raw_references:
        reference = _normalized_source_path(raw_reference)
        if reference:
            references.append(reference)
    return tuple(references)


def _dotenv_visible_to_reference(dotenv_source: str, reference: str) -> bool:
    if not reference or reference.startswith("_scan_only/") or reference.startswith(".temp/"):
        return False
    source_path = PurePosixPath(dotenv_source)
    source_parent = source_path.parent.as_posix()
    if source_parent == ".":
        return True
    reference_path = PurePosixPath(reference)
    reference_parent = reference_path.parent.as_posix()
    return reference == source_parent or reference.startswith(f"{source_parent}/") or reference_parent == source_parent


def _runtime_config_scope(source: str) -> str:
    parts = PurePosixPath(source).parts
    if len(parts) >= 2 and parts[0] in {".claude", ".codex", ".openclaw"}:
        return parts[0]
    if _is_settings_env_source(source):
        return PurePosixPath(source).parent.as_posix()
    return ""


def _settings_visible_to_reference(settings_source: str, reference: str) -> bool:
    if not reference:
        return False
    if reference == settings_source:
        return True
    scope = _runtime_config_scope(settings_source)
    if not scope:
        return False
    reference_scope = _runtime_config_scope(reference)
    return bool(reference_scope and reference_scope == scope)


def _env_config_duplicate_matches(env_entry: dict, generic_entry: dict) -> bool:
    generic_field = _env_config_field(generic_entry)
    env_field = str(env_entry.get("field", "") or "").strip()
    if not generic_field or generic_field != env_field:
        return False
    generic_source = _normalized_source_path(generic_entry.get("source"))
    if not generic_source:
        return False
    references = _referenced_in(env_entry)
    if _is_dotenv_source(generic_source):
        if not references:
            return False
        return any(_dotenv_visible_to_reference(generic_source, reference) for reference in references)
    if _is_settings_env_source(generic_source):
        if not references:
            return _runtime_config_scope(generic_source) in {".claude", ".codex", ".openclaw"}
        return any(_settings_visible_to_reference(generic_source, reference) for reference in references)
    return False


def _is_duplicate_env_var_entry(env_entry: dict, generic_entries: list) -> bool:
    return any(
        isinstance(generic_entry, dict) and _env_config_duplicate_matches(env_entry, generic_entry)
        for generic_entry in generic_entries
    )


def _strip_tracking_exclude_entry(entry: dict, *, index: int) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise ValueError("reviewed_scan_payload.excludes items must be objects")
    raw_source = entry.get("source")
    if not isinstance(raw_source, str):
        raise ValueError(f"reviewed_scan_payload.excludes[{index}].source must be a string")
    source = raw_source.strip()
    if not source:
        raise ValueError(f"reviewed_scan_payload.excludes[{index}].source must not be empty")
    return {
        "source": source,
        "use": _require_reviewed_use(entry, label=f"reviewed_scan_payload.excludes[{index}]"),
    }


def build_config_keys_request(
    agent_version_id: str,
    reviewed_scan_payload: dict,
) -> dict[str, Any]:
    if not str(agent_version_id or "").strip():
        raise ValueError("agent_version_id must not be empty")
    if not isinstance(reviewed_scan_payload, dict):
        raise ValueError("reviewed_scan_payload must be an object")
    reviewed_scan_payload = sanitize_reviewed_scan_payload(reviewed_scan_payload)

    url_proxy = reviewed_scan_payload.get("url_proxy")
    generic = reviewed_scan_payload.get("generic")
    env_vars = reviewed_scan_payload.get("env_var")
    excludes = reviewed_scan_payload.get("excludes", [])

    if not isinstance(url_proxy, list):
        raise ValueError("reviewed_scan_payload.url_proxy must be an array")
    if not isinstance(generic, list):
        raise ValueError("reviewed_scan_payload.generic must be an array")
    if not isinstance(env_vars, list):
        raise ValueError("reviewed_scan_payload.env_var must be an array")
    if "excludes" in reviewed_scan_payload and not isinstance(excludes, list):
        raise ValueError("reviewed_scan_payload.excludes must be an array")

    uploadable_generic_entries = [
        entry
        for entry in generic
        if _is_uploadable_generic_entry(entry)
    ]

    credentials_payload: dict[str, Any] = {
        "url_proxy": [
            _strip_tracking_url_proxy_entry(entry, index=index)
            for index, entry in enumerate(url_proxy)
        ],
        "generic": [
            _strip_tracking_generic_entry(entry, index=index)
            for index, entry in enumerate(generic)
            if _is_uploadable_generic_entry(entry)
        ],
        "env_var": [
            _strip_tracking_env_var_entry(entry, index=index)
            for index, entry in enumerate(env_vars)
            if not (
                isinstance(entry, dict)
                and _is_duplicate_env_var_entry(entry, uploadable_generic_entries)
            )
        ],
        "excludes": [
            _strip_tracking_exclude_entry(entry, index=index)
            for index, entry in enumerate(excludes)
        ],
    }

    return {
        "agentVersionId": str(agent_version_id).strip(),
        "requiredCredentials": json.dumps(credentials_payload, ensure_ascii=False),
    }


__all__ = ["build_config_keys_request"]
