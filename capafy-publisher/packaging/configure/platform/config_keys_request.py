from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Optional

from capafy_platform.api import save_config_keys_raw
from packaging._shared.contracts.reviewed_scan import (
    require_reviewed_scan_use as _require_reviewed_use,
    sanitize_reviewed_scan_payload,
)
from packaging._shared.platform.response_normalize import (
    attach_platform_status,
    normalize_edit_link_response,
)
from packaging.configure.scan.scan_only_paths import is_scan_only_source_path


def _strip_tracking_source(item: dict, *, label: str) -> str:
    raw_source = item.get("source")
    if not isinstance(raw_source, str):
        raise ValueError(f"{label}.source must be a string")
    source = raw_source.strip()
    if not source:
        raise ValueError(f"{label}.source must not be empty")
    return source


_DOT_AGENT_DEFAULT_FIELDS = {
    "codex": ("OPENAI_API_KEY", "OPENAI_BASE_URL"),
    "claude_code": ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL"),
}


def _minimal_dot_agent_url_proxy_entry(
    entry: dict,
    *,
    index: int,
    env_id: str,
) -> dict[str, Any]:
    api_key = entry.get("api_key")
    url = entry.get("url")
    if not isinstance(api_key, dict):
        raise ValueError(f"reviewed_scan_payload.url_proxy[{index}].api_key must be an object")
    if not isinstance(url, dict):
        raise ValueError(f"reviewed_scan_payload.url_proxy[{index}].url must be an object")
    api_format = str(entry.get("api_format", "") or "").strip()
    if not api_format:
        raise ValueError(f"reviewed_scan_payload.url_proxy[{index}].api_format must not be empty")
    default_key_field, default_url_field = _DOT_AGENT_DEFAULT_FIELDS[env_id]
    return {
        # Keep platform-managed identities while never uploading the local API key.
        "api_key": {
            "value": "",
            "placeholder": str(api_key.get("placeholder", "") or "").strip(),
            "field": default_key_field,
        },
        "url": {
            "value": url.get("value", ""),
            "placeholder": str(url.get("placeholder", "") or "").strip(),
            "field": default_url_field,
        },
        "model": str(entry.get("model", "") or "").strip(),
        "api_format": api_format,
    }


def _strip_tracking_url_proxy_entry(
    entry: dict,
    *,
    index: int,
    env_id: str = "",
) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise ValueError("reviewed_scan_payload.url_proxy items must be objects")
    if env_id in {"codex", "claude_code"}:
        return _minimal_dot_agent_url_proxy_entry(entry, index=index, env_id=env_id)
    api_key = entry.get("api_key")
    url = entry.get("url")
    if not isinstance(api_key, dict):
        raise ValueError(f"reviewed_scan_payload.url_proxy[{index}].api_key must be an object")
    if not isinstance(url, dict):
        raise ValueError(f"reviewed_scan_payload.url_proxy[{index}].url must be an object")
    projected: dict[str, Any] = {
        "api_key": {
            "value": "",
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
    provider_name = str(entry.get("provider_name", "") or "").strip()
    if provider_name:
        projected["provider_name"] = provider_name
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


def build_config_keys_request(
    agent_version_id: str,
    reviewed_scan_payload: dict,
) -> dict[str, Any]:
    if not str(agent_version_id or "").strip():
        raise ValueError("agent_version_id must not be empty")
    if not isinstance(reviewed_scan_payload, dict):
        raise ValueError("reviewed_scan_payload must be an object")
    review_metadata = reviewed_scan_payload.get("_review")
    env_id = (
        str(review_metadata.get("env_id", "") or "").strip()
        if isinstance(review_metadata, dict)
        else ""
    )
    reviewed_scan_payload = sanitize_reviewed_scan_payload(reviewed_scan_payload)

    url_proxy = reviewed_scan_payload.get("url_proxy")
    generic = reviewed_scan_payload.get("generic")

    if not isinstance(url_proxy, list):
        raise ValueError("reviewed_scan_payload.url_proxy must be an array")
    if not isinstance(generic, list):
        raise ValueError("reviewed_scan_payload.generic must be an array")

    credentials_payload: dict[str, Any] = {
        "url_proxy": [
            _strip_tracking_url_proxy_entry(entry, index=index, env_id=env_id)
            for index, entry in enumerate(url_proxy)
        ],
        "generic": _project_unique_generic_entries(generic),
    }

    return {
        "agentVersionId": str(agent_version_id).strip(),
        "requiredCredentials": json.dumps(credentials_payload, ensure_ascii=False),
    }


def save_config_keys(
    agent_id: str,
    agent_version_id: str,
    reviewed_scan_payload: dict,
    *,
    access_token: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict[str, Any]:
    normalized_agent_id = str(agent_id or "").strip()
    if not normalized_agent_id:
        raise ValueError("agent_id must not be empty")
    request_body = build_config_keys_request(agent_version_id, reviewed_scan_payload)
    data = save_config_keys_raw(
        normalized_agent_id,
        request_body,
        access_token=access_token,
        base_url=base_url,
    )
    response = normalize_edit_link_response(
        "save_config_keys",
        request_body,
        data,
        base_url=base_url,
        agent_id=normalized_agent_id,
    )
    return attach_platform_status(response, data, workflow_status="pending_config_confirmation")


__all__ = ["build_config_keys_request", "save_config_keys"]
