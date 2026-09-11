from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Optional

from packaging.publish.reviewed_scan import (
    require_reviewed_scan_use as _require_reviewed_use,
    sanitize_reviewed_scan_payload,
)
from packaging.publish.platform.environment_selection import forbidden_environment_names_for_runtime
from packaging.publish.security.scan.scan_only_paths import is_scan_only_source_path


def _strip_tracking_source(item: dict, *, label: str) -> str:
    raw_source = item.get("source")
    if not isinstance(raw_source, str):
        raise ValueError(f"{label}.source must be a string")
    source = raw_source.strip()
    if not source:
        raise ValueError(f"{label}.source must not be empty")
    return source


def _api_key_descriptor(
    entry: dict[str, Any],
) -> Optional[dict[str, str]]:
    """Project non-sensitive runtime key identity into the review schema."""
    identity = entry.get("_api_key_identity")
    if not isinstance(identity, dict):
        return None
    field = str(identity.get("field", "") or "").strip()
    placeholder = str(identity.get("placeholder", "") or "").strip()
    if not field or not placeholder:
        return None
    return {"value": "", "placeholder": placeholder, "field": field}


def _strip_tracking_url_proxy_entry(
    entry: dict,
    *,
    index: int,
) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise ValueError("reviewed_scan_payload.url_proxy items must be objects")
    url = entry.get("url")
    if not isinstance(url, dict):
        raise ValueError(f"reviewed_scan_payload.url_proxy[{index}].url must be an object")
    api_format = str(entry.get("api_format", "") or "").strip()
    if not api_format:
        raise ValueError(f"reviewed_scan_payload.url_proxy[{index}].api_format must not be empty")
    source = _strip_tracking_source(url, label=f"reviewed_scan_payload.url_proxy[{index}].url")
    projected = {
        "url": {
            "value": url.get("value", ""),
            "placeholder": str(url.get("placeholder", "") or "").strip(),
            "field": url.get("field", ""),
            "source": source,
        },
        "model": str(entry.get("model", "") or "").strip(),
        "api_format": api_format,
    }
    projected["use"] = _require_reviewed_use(entry, label=f"reviewed_scan_payload.url_proxy[{index}]")
    api_key = _api_key_descriptor(entry)
    if api_key is not None:
        projected["api_key"] = api_key
    provider_name = str(entry.get("provider_name", "") or "").strip()
    if provider_name:
        projected["provider_name"] = provider_name
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


def _qualified_generic_field(entry: dict[str, Any]) -> str:
    field = str(entry.get("field", "") or "").strip()
    source = str(entry.get("source", "") or "").strip()
    source_detail = str(entry.get("source_detail", "") or "").strip()
    if not field or not source_detail.startswith(("json:", "yaml:", "toml:")):
        return ""
    detail_path = (
        source_detail.split(":", 1)[1]
        .strip()
        .replace("~1", "/")
        .replace("~0", "~")
    )
    readable = re.sub(r"[^A-Za-z0-9_.-]+", "_", detail_path).strip("_.-")
    digest = (
        hashlib.sha256(f"{source}\n{source_detail}".encode("utf-8"))
        .hexdigest()
        .upper()[:8]
    )
    readable_suffix = readable[-64:] if readable else "location"
    field_prefix = field[:40]
    return f"{field_prefix}__{readable_suffix}__{digest}"


def _project_unique_generic_entries(generic: list[Any]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for index, entry in enumerate(generic):
        if not _is_uploadable_generic_entry(entry):
            continue
        projected = _strip_tracking_generic_entry(entry, index=index)
        field = str(projected.get("field", "") or "").strip()
        grouped.setdefault(field, []).append(projected)

    result: list[dict[str, Any]] = []
    for field, entries in grouped.items():
        if not field or len(entries) == 1:
            result.extend(entries)
            continue

        identities = {
            (
                str(entry.get("value", "") or ""),
                str(entry.get("placeholder", "") or "").strip(),
            )
            for entry in entries
        }
        if len(identities) == 1:
            result.append(entries[0])
            continue

        qualified_fields = [_qualified_generic_field(entry) for entry in entries]
        if all(qualified_fields) and len(set(qualified_fields)) == len(qualified_fields):
            for entry, qualified_field in zip(entries, qualified_fields):
                qualified = dict(entry)
                qualified["field"] = qualified_field
                result.append(qualified)
            continue

        sources = [str(entry.get("source", "") or "").strip() for entry in entries]
        unique_sources = list(dict.fromkeys(source for source in sources if source))
        source_summary = ", ".join(unique_sources)
        if not source_summary:
            source_summary = "unknown"
        raise ValueError(
            f"reviewed_scan_payload.generic field must be unique: {field}; "
            f"conflicting sources: {source_summary}"
        )
    return result


def _project_environment_variables(
    environment_variables: object,
    *,
    env_id: str = "",
) -> list[dict[str, str]]:
    if environment_variables is None:
        return []
    if not isinstance(environment_variables, list):
        raise ValueError("environment_variables must be an array")
    projected: list[dict[str, str]] = []
    seen: set[str] = set()
    forbidden_names = forbidden_environment_names_for_runtime(env_id)
    for index, entry in enumerate(environment_variables):
        if not isinstance(entry, dict):
            raise ValueError(f"environment_variables[{index}] must be an object")
        field = str(entry.get("field", "") or "").strip()
        value = entry.get("value")
        use = str(entry.get("use", "") or "").strip()
        if not field:
            raise ValueError(f"environment_variables[{index}].field must not be empty")
        if field.upper() in forbidden_names:
            raise ValueError(
                f"environment variable is forbidden for {str(env_id or '').strip() or 'this upload'}: "
                f"{field}"
            )
        if field in seen:
            raise ValueError(f"environment variable field must be unique: {field}")
        if not isinstance(value, str) or not value:
            raise ValueError(f"environment_variables[{index}].value must not be empty")
        if not use:
            raise ValueError(f"environment_variables[{index}].use must not be empty")
        seen.add(field)
        projected.append(
            {
                "field": field,
                "value": value,
                "use": use,
            }
        )
    return projected


def build_required_credentials(
    reviewed_scan_payload: dict,
    *,
    environment_variables: Optional[list[dict[str, str]]] = None,
    env_id: str = "",
) -> str:
    if not isinstance(reviewed_scan_payload, dict):
        raise ValueError("reviewed_scan_payload must be an object")
    reviewed_scan_payload = sanitize_reviewed_scan_payload(reviewed_scan_payload)

    url_proxy = reviewed_scan_payload.get("url_proxy")
    generic = reviewed_scan_payload.get("generic")

    if not isinstance(url_proxy, list):
        raise ValueError("reviewed_scan_payload.url_proxy must be an array")
    if not isinstance(generic, list):
        raise ValueError("reviewed_scan_payload.generic must be an array")

    credentials_payload: dict[str, Any] = {
        "url_proxy": [
            _strip_tracking_url_proxy_entry(entry, index=index)
            for index, entry in enumerate(url_proxy)
        ],
        "generic": _project_unique_generic_entries(generic),
    }
    projected_environment_variables = _project_environment_variables(
        environment_variables,
        env_id=env_id,
    )
    if projected_environment_variables:
        credentials_payload["env_var"] = projected_environment_variables

    return json.dumps(credentials_payload, ensure_ascii=False)


__all__ = ["build_required_credentials"]
