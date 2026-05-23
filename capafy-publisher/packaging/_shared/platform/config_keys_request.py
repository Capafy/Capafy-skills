from __future__ import annotations

import json
from typing import Any

from packaging._shared.contracts.reviewed_scan import (
    project_env_var_credentials_item,
    sanitize_reviewed_scan_payload,
)
from packaging.configure.scan.scan_only_paths import is_scan_only_source_path


def _strip_tracking_source(item: dict, *, label: str) -> str:
    source = str(item.get("source", "") or "").strip()
    if not source:
        raise ValueError(f"{label}.source must not be empty")
    return source


def _require_reviewed_use(entry: dict, *, label: str) -> str:
    use = str(entry.get("use", "")).strip()
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


def _is_scan_only_source(source: str) -> bool:
    return is_scan_only_source_path(source)


def _strip_tracking_env_var_entry(entry: dict, *, index: int) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise ValueError("reviewed_scan_payload.env_var items must be objects")
    return project_env_var_credentials_item(entry, label=f"reviewed_scan_payload.env_var[{index}]")


def _strip_tracking_exclude_entry(entry: dict, *, index: int) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise ValueError("reviewed_scan_payload.excludes items must be objects")
    source = str(entry.get("source", "")).strip()
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

    credentials_payload: dict[str, Any] = {
        "url_proxy": [
            _strip_tracking_url_proxy_entry(entry, index=index)
            for index, entry in enumerate(url_proxy)
        ],
        "generic": [
            _strip_tracking_generic_entry(entry, index=index)
            for index, entry in enumerate(generic)
            if not (
                isinstance(entry, dict)
                and _is_scan_only_source(str(entry.get("source", "") or ""))
            )
        ],
        "env_var": [
            _strip_tracking_env_var_entry(entry, index=index)
            for index, entry in enumerate(env_vars)
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
