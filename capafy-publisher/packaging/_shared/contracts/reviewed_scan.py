from __future__ import annotations

import json
from typing import Any, Iterable, List, Mapping, TypedDict


REVIEW_METADATA_KEY = "_review"
REVIEW_STATUS_REVIEWED = "reviewed"
REVIEW_BINDING_FIELDS = (
    "raw_scan_digest",
    "staging_digest",
    "scan_only_digest",
    "env_id",
    "agent_type",
)
CLOUD_HOSTED_URL_PROXY_REQUIRED_MESSAGE = (
    "cloud_hosted requires at least 1 url_proxy; "
    "platform cloud hosting requires the creator to provide an LLM provider endpoint plus API key"
)


class ScanItem(TypedDict, total=False):
    field: str
    url: str
    value: str
    source: str
    placeholder: str
    value_type: str
    use: str
    referenced_in: List[str]
    source_detail: str
    occurrence_index: int
    field_aliases: List[str]


class UrlProxyEntry(TypedDict, total=False):
    api_key: ScanItem
    url: ScanItem
    model: str
    api_format: str


class ReviewMetadata(TypedDict, total=False):
    reviewer: str
    status: str
    raw_scan_digest: str
    staging_digest: str
    scan_only_digest: str
    env_id: str
    agent_type: str


class ScanGroups(TypedDict, total=False):
    url_proxy: List[UrlProxyEntry]
    generic: List[ScanItem]
    env_var: List[ScanItem]


class ReviewedScan(ScanGroups, total=False):
    excludes: List[dict]
    _review: ReviewMetadata


def sanitize_reviewed_scan_payload(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(payload)
    cleaned.pop(REVIEW_METADATA_KEY, None)
    return cleaned


def credential_counts(scan_payload: dict) -> dict:
    counts: dict = {}
    for key in ("url_proxy", "generic", "env_var", "excludes"):
        value = scan_payload.get(key, [])
        counts[key] = len(value) if isinstance(value, list) else 0
    return counts


def require_cloud_hosted_url_proxy_entries(scan_payload: object) -> object:
    if not isinstance(scan_payload, dict):
        raise ValueError(CLOUD_HOSTED_URL_PROXY_REQUIRED_MESSAGE)
    value = scan_payload.get("url_proxy", [])
    if not isinstance(value, list) or not any(isinstance(item, dict) for item in value):
        raise ValueError(CLOUD_HOSTED_URL_PROXY_REQUIRED_MESSAGE)
    return scan_payload


def _review_metadata_has_binding_fields(metadata: dict, fields: tuple) -> bool:
    return all(str(metadata.get(field, "")).strip() for field in fields)


def is_reviewed_scan_payload(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    metadata = payload.get(REVIEW_METADATA_KEY)
    if not isinstance(metadata, dict):
        return False
    reviewer = str(metadata.get("reviewer", "")).strip()
    status = str(metadata.get("status", "")).strip()
    if not reviewer or status != REVIEW_STATUS_REVIEWED:
        return False
    return _review_metadata_has_binding_fields(metadata, REVIEW_BINDING_FIELDS)


def resolved_review_binding(
    *,
    review_binding: dict | None = None,
    raw_scan: dict | None = None,
    staging_root: object = None,
    env_id: str | None = None,
    agent_type: str | None = None,
    digest_builder: object = None,
) -> dict:
    resolved: dict = {}
    if isinstance(review_binding, dict):
        for field in REVIEW_BINDING_FIELDS:
            value = str(review_binding.get(field, "")).strip()
            if value:
                resolved[field] = value
    if digest_builder is not None:
        if "raw_scan_digest" not in resolved and raw_scan is not None:
            resolved["raw_scan_digest"] = digest_builder.raw_scan(raw_scan)
        if "staging_digest" not in resolved and staging_root is not None:
            resolved["staging_digest"] = digest_builder.staging(staging_root)
        if "scan_only_digest" not in resolved and staging_root is not None:
            resolved["scan_only_digest"] = digest_builder.scan_only(staging_root)
    if "env_id" not in resolved and env_id is not None:
        resolved["env_id"] = str(env_id or "").strip()
    if "agent_type" not in resolved and agent_type is not None:
        resolved["agent_type"] = str(agent_type or "").strip()
    return resolved


def reviewed_scan_matches_context(
    payload: object,
    *,
    review_binding: dict | None = None,
    raw_scan: dict | None = None,
    staging_root: object = None,
    env_id: str | None = None,
    agent_type: str | None = None,
    digest_builder: object = None,
) -> bool:
    if not is_reviewed_scan_payload(payload):
        return False
    metadata = payload[REVIEW_METADATA_KEY]  # type: ignore[index]

    expected = resolved_review_binding(
        review_binding=review_binding,
        raw_scan=raw_scan,
        staging_root=staging_root,
        env_id=env_id,
        agent_type=agent_type,
        digest_builder=digest_builder,
    )

    for field, value in expected.items():
        if str(metadata.get(field, "")).strip() != value:
            return False
    return True


def reviewed_scan_context_diagnostics(
    payload: object,
    *,
    review_binding: dict | None = None,
) -> dict[str, Any]:
    expected = resolved_review_binding(
        review_binding=review_binding,
    )
    metadata = payload.get(REVIEW_METADATA_KEY, {}) if isinstance(payload, dict) else {}
    reviewed = {
        field: str(metadata.get(field, "")).strip()
        for field in expected
        if isinstance(metadata, dict)
    }
    mismatches = [
        {
            "field": field,
            "reviewed": reviewed.get(field, ""),
            "current": value,
        }
        for field, value in expected.items()
        if reviewed.get(field, "") != value
    ]
    return {
        "current": expected,
        "reviewed": reviewed,
        "mismatches": mismatches,
    }










def collect_api_key_items(payload: ScanGroups) -> List[ScanItem]:
    items: List[ScanItem] = []
    url_proxy_items = payload.get("url_proxy", [])
    if isinstance(url_proxy_items, list):
        for entry in url_proxy_items:
            if not isinstance(entry, dict):
                continue
            api_key = entry.get("api_key")
            if isinstance(api_key, dict):
                items.append(dict(api_key))  # type: ignore[arg-type]
    return items


def collect_runtime_value_items(payload: ScanGroups) -> List[ScanItem]:
    items: List[ScanItem] = []

    url_proxy_items = payload.get("url_proxy", [])
    if isinstance(url_proxy_items, list):
        for entry in url_proxy_items:
            if not isinstance(entry, dict):
                continue
            url = entry.get("url")
            if isinstance(url, dict):
                items.append(dict(url))  # type: ignore[arg-type]

    generic_items = payload.get("generic", [])
    if isinstance(generic_items, list):
        for entry in generic_items:
            if isinstance(entry, dict):
                items.append(dict(entry))  # type: ignore[arg-type]

    return items


def _string_value(value: object) -> str:
    return "" if value is None else str(value)


def _required_non_empty_text(entry: Mapping[str, Any], key: str, *, label: str) -> str:
    value = str(entry.get(key, "") or "").strip()
    if not value:
        raise ValueError(f"{label}.{key} must not be empty")
    return value


def _required_reviewed_scan_use(entry: Mapping[str, Any], *, label: str) -> str:
    use = str(entry.get("use", "") or "").strip()
    if not use:
        raise ValueError(f"{label}.use must not be empty for reviewed_scan")
    return use


def build_reviewed_env_var_item(
    *,
    field: str,
    value: object,
    use: str,
    placeholder: object = "",
    referenced_in: Iterable[object] = (),
) -> ScanItem:
    normalized_field = str(field or "").strip()
    if not normalized_field:
        raise ValueError("reviewed_scan.env_var.field must not be empty")
    return {
        "field": normalized_field,
        "value": _string_value(value),
        "placeholder": _string_value(placeholder),
        "referenced_in": [str(item) for item in referenced_in if str(item).strip()],
        "use": str(use or "").strip(),
    }


def project_env_var_credentials_item(entry: Mapping[str, Any], *, label: str) -> dict[str, Any]:
    field = _required_non_empty_text(entry, "field", label=label)
    return {
        "field": field,
        "value": entry.get("value", ""),
        "use": _required_reviewed_scan_use(entry, label=label),
    }







def required_list(payload: dict, key: str, *, label: str) -> list:
    if key not in payload:
        raise ValueError(f"{label}.{key} must be an array")
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"{label}.{key} must be an array")
    return value


def _parse_reviewed_scan(payload: object, *, label: str = "reviewed_scan") -> ReviewedScan:
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be an object")
    parsed: ReviewedScan = {
        "url_proxy": required_list(payload, "url_proxy", label=label),
        "generic": required_list(payload, "generic", label=label),
        "env_var": required_list(payload, "env_var", label=label),
        "excludes": required_list(payload, "excludes", label=label),
    }
    metadata = payload.get(REVIEW_METADATA_KEY)
    if isinstance(metadata, dict):
        parsed[REVIEW_METADATA_KEY] = metadata
    return parsed


def validate_reviewed_scan_gate(reviewed_scan_payload: object, *, label: str = "reviewed_scan") -> None:
    _parse_reviewed_scan(reviewed_scan_payload, label=label)


def _normalize_source_field(item: dict) -> str:
    source = str(item.get("source", "") or "").strip()
    if not source:
        return ""
    if " -> " in source or " → " in source or " line " in source:
        raise ValueError("source must not contain derived arrows or line markers")
    return source


def _normalize_occurrence_index(item: Mapping[str, Any], *, label: str) -> int:
    raw = item.get("occurrence_index")
    if raw is None or str(raw).strip() == "":
        return 0
    if isinstance(raw, bool):
        raise ValueError(f"{label}.occurrence_index must be a positive integer")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{label}.occurrence_index must be a positive integer") from None
    if value <= 0:
        raise ValueError(f"{label}.occurrence_index must be a positive integer")
    return value


def _optional_list_field(item: dict, key: str) -> list:
    value = item.get(key)
    return list(value) if isinstance(value, list) else []


def _normalize_single_item(item: dict, label: str, *, include_value_type: bool = False) -> ScanItem:
    source = _normalize_source_field(item)

    normalized: ScanItem = {
        "field": str(item.get("field", "")),
        "url": str(item.get("url", "")),
        "value": str(item.get("value", "")),
        "source": source,
        "source_detail": str(item.get("source_detail", "") or ""),
        "occurrence_index": _normalize_occurrence_index(item, label=label),
        "placeholder": str(item.get("placeholder", "")),
    }
    if include_value_type:
        normalized["value_type"] = str(item.get("value_type", ""))
    normalized["field_aliases"] = [str(x) for x in _optional_list_field(item, "field_aliases")]
    return normalized


def _assign_occurrence_indexes(items: list[ScanItem]) -> list[ScanItem]:
    counters: dict[tuple[str, str, str], int] = {}
    for item in items:
        key = (
            str(item.get("source", "")).strip(),
            str(item.get("field", "")).strip(),
            str(item.get("value_type", "") or "").strip(),
        )
        current = int(item.get("occurrence_index", 0) or 0)
        if current > 0:
            counters[key] = max(counters.get(key, 0), current)
            continue
        next_index = counters.get(key, 0) + 1
        item["occurrence_index"] = next_index
        counters[key] = next_index
    return items


def load_reviewed_scan_payload(raw_json: str, *, label: str = "reviewed_scan_json") -> object:
    try:
        return json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"failed to parse {label}: {exc}") from exc


def normalize_reviewed_scan_payload(
    reviewed_scan_payload: object,
    *,
    label: str = "reviewed_scan",
) -> tuple:
    parsed = _parse_reviewed_scan(reviewed_scan_payload, label=label)


    key_items: List[ScanItem] = [
        _normalize_single_item(item, "url_proxy.api_key")
        for item in collect_api_key_items(parsed)
    ]
    runtime_values: List[ScanItem] = [
        _normalize_single_item(item, "generic", include_value_type=True)
        for item in collect_runtime_value_items(parsed)
    ]
    _assign_occurrence_indexes(key_items)
    _assign_occurrence_indexes(runtime_values)

    for item in [*key_items, *runtime_values]:
        if int(item.get("occurrence_index", 0) or 0) <= 0:
            raise ValueError(f"{label}.occurrence_index must be a positive integer")

    for key in key_items:
        source = str(key.get("source", "")).strip()
        value = str(key.get("value", ""))
        placeholder = str(key.get("placeholder", ""))
        if not value and not placeholder:
            raise ValueError("url_proxy.api_key requires a value or a platform-managed placeholder")
        if not source:
            raise ValueError("url_proxy.api_key requires every item to include a non-empty source")
    for runtime_value in runtime_values:
        source = str(runtime_value.get("source", "")).strip()
        value = str(runtime_value.get("value", ""))
        placeholder = str(runtime_value.get("placeholder", ""))
        if not value and not placeholder:
            raise ValueError("runtime_values items must include a value or a platform-managed placeholder")
        if not source:
            raise ValueError("generic requires every item to include a non-empty source")

    return key_items, runtime_values


def summarize_reviewed_scan_deploy_items(key_items: list, runtime_values: list) -> dict:
    return {
        "api_keys_count": len(key_items),
        "runtime_values_count": len(runtime_values),
        "total_count": len(key_items) + len(runtime_values),
    }


__all__ = [
    "CLOUD_HOSTED_URL_PROXY_REQUIRED_MESSAGE",
    "REVIEW_BINDING_FIELDS",
    "REVIEW_METADATA_KEY",
    "REVIEW_STATUS_REVIEWED",
    "ReviewMetadata",
    "ReviewedScan",
    "ScanGroups",
    "ScanItem",
    "UrlProxyEntry",
    "build_reviewed_env_var_item",
    "collect_api_key_items",
    "collect_runtime_value_items",
    "credential_counts",
    "is_reviewed_scan_payload",
    "load_reviewed_scan_payload",
    "normalize_reviewed_scan_payload",
    "project_env_var_credentials_item",
    "require_cloud_hosted_url_proxy_entries",
    "required_list",
    "resolved_review_binding",
    "reviewed_scan_context_diagnostics",
    "reviewed_scan_matches_context",
    "sanitize_reviewed_scan_payload",
    "summarize_reviewed_scan_deploy_items",
    "validate_reviewed_scan_gate",
]
