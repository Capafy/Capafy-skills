from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING, Union

from packaging.publish.reviewed_scan import (
    REVIEW_METADATA_KEY,
    REVIEW_STATUS_REVIEWED,
    compute_scan_digest,
    compute_staging_digest,
    is_reviewed_scan_payload,
)
from packaging.publish.security.scan.entries import use_for_generic_value
from packaging.publish.staging.source_boundary import filter_generic_payload_items

if TYPE_CHECKING:
    from packaging.runtime.contracts import ReviewedScanBuildInput


def _copy_dict_list(items: object) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [dict(item) for item in items if isinstance(item, dict)]


def build_review_binding(
    *,
    raw_scan: dict[str, Any],
    staging_root: Union[str, Path],
    env_id: str,
    agent_type: str,
) -> dict[str, str]:
    return {
        "raw_scan_digest": compute_scan_digest(raw_scan),
        "staging_digest": compute_staging_digest(staging_root),
        "env_id": str(env_id or "").strip(),
        "agent_type": str(agent_type or "").strip(),
    }


def refresh_reviewed_scan_metadata(
    payload: Union[dict[str, Any], object],
    *,
    staging_root: Union[str, Path],
    env_id: str,
    agent_type: str,
) -> Union[dict[str, Any], object]:
    if not isinstance(payload, dict) or not is_reviewed_scan_payload(payload):
        return payload

    existing_metadata = payload.get(REVIEW_METADATA_KEY)
    if not isinstance(existing_metadata, dict):
        return payload

    resolved_binding = {
        "staging_digest": compute_staging_digest(staging_root),
        "env_id": str(env_id or "").strip(),
        "agent_type": str(agent_type or "").strip(),
    }
    metadata = dict(existing_metadata)

    substantive_change = False
    for field, value in resolved_binding.items():
        current_value = str(metadata.get(field, "")).strip()
        if not current_value:
            metadata[field] = value
            substantive_change = True
            continue
        if current_value != value:
            metadata[field] = value
            substantive_change = True

    existing_digest = str(existing_metadata.get("reviewed_scan_digest", "")).strip()
    content_digest_changed = False
    if existing_digest:
        candidate = dict(payload)
        candidate[REVIEW_METADATA_KEY] = metadata
        current_digest = compute_scan_digest(candidate)
        content_digest_changed = current_digest != existing_digest

    if not substantive_change and not content_digest_changed:
        return payload

    refreshed = dict(payload)
    refreshed[REVIEW_METADATA_KEY] = metadata
    metadata["reviewed_scan_digest"] = compute_scan_digest(refreshed)
    return refreshed


def _review_metadata_template(review_binding: dict[str, str]) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "reviewer": "rules_scan",
        "status": REVIEW_STATUS_REVIEWED,
    }
    metadata.update(review_binding)
    return metadata


def _list_payload(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key, [])
    return _copy_dict_list(value) if isinstance(value, list) else []


def _generic_payload(payload: dict[str, Any], *, staging_root: Union[str, Path], agent_type: str) -> list[Any]:
    resolved_agent_type = str(agent_type or "").strip()
    if not resolved_agent_type:
        raise ValueError("reviewed scan source filtering requires agent_type")
    return filter_generic_payload_items(
        _list_payload(payload, "generic"),
        staging_root=staging_root,
        agent_type=resolved_agent_type,
    )


def build_reviewed_scan_from_scan(
    raw_scan: dict[str, Any],
    *,
    review_binding: dict[str, str],
    staging_root: Union[str, Path],
) -> dict[str, Any]:
    agent_type = str(review_binding.get("agent_type", "")).strip()
    if not agent_type:
        raise ValueError("review_binding.agent_type is required")
    reviewed_scan = {
        "url_proxy": _list_payload(raw_scan, "url_proxy"),
        "generic": _generic_payload(raw_scan, staging_root=staging_root, agent_type=agent_type),
        REVIEW_METADATA_KEY: _review_metadata_template(review_binding),
    }
    return reviewed_scan


def build_reviewed_scan_from_input(
    reviewed_input: ReviewedScanBuildInput,
    *,
    review_binding: dict[str, str],
) -> dict[str, Any]:
    url_proxy_items: list[dict[str, Any]] = []
    for route in reviewed_input.url_proxy_pairs:
        item = {
            "url": {
                "value": route.url.original_value,
                "placeholder": route.url.placeholder,
                "field": route.url.field,
                "source": route.url.source_identity(),
                "source_detail": route.url.source_detail_identity(),
                "occurrence_index": route.url.occurrence_index_identity(),
                "value_type": "url",
                "url": route.url.original_value or route.url.placeholder,
            },
            "url_proxy_group": route.group,
            "use": f"LLM endpoint for {route.provider_name or route.service}",
        }
        model = str(route.model or "").strip()
        api_format = str(route.api_format or "").strip()
        if model:
            item["model"] = model
        if api_format:
            item["api_format"] = api_format
        provider_name = str(route.provider_name or "").strip()
        if provider_name:
            item["provider_name"] = provider_name
        if route.api_key is not None:
            item["_api_key_identity"] = {
                "field": route.api_key.field,
                "placeholder": route.api_key.placeholder,
                "source": route.api_key.source_identity(),
                "source_detail": route.api_key.source_detail_identity(),
                "occurrence_index": route.api_key.occurrence_index_identity(),
            }
        url_proxy_items.append(item)

    generic_items: list[dict[str, Any]] = []
    for generic_value in reviewed_input.generic_values:
        source = str(generic_value.source_relpath or "").strip()
        if not source:
            continue
        generic_items.append(
            {
                "value": generic_value.original_value,
                "placeholder": generic_value.placeholder,
                "field": generic_value.field,
                "source": source,
                "source_detail": generic_value.location.to_source_detail(generic_value.field),
                "occurrence_index": generic_value.location.occurrence_index_identity(),
                "value_type": generic_value.value_type,
                "use": use_for_generic_value(generic_value.field, generic_value.value_type),
            }
        )

    return {
        "url_proxy": url_proxy_items,
        "generic": generic_items,
        REVIEW_METADATA_KEY: _review_metadata_template(review_binding),
    }


__all__ = [
    "build_review_binding",
    "build_reviewed_scan_from_input",
    "build_reviewed_scan_from_scan",
    "refresh_reviewed_scan_metadata",
]
