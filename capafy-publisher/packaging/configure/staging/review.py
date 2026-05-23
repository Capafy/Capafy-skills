from __future__ import annotations

from pathlib import Path
from typing import Any

from packaging._shared.contracts.reviewed_scan import (
    REVIEW_METADATA_KEY,
    REVIEW_STATUS_REVIEWED,
    is_reviewed_scan_payload,
    resolved_review_binding as _contract_resolved_review_binding,
    reviewed_scan_matches_context as _contract_reviewed_scan_matches_context,
    sanitize_reviewed_scan_payload,
)
from packaging._shared.reviewed_scan.digest import (
    compute_scan_digest,
    compute_scan_only_digest,
    compute_staging_digest,
)
from packaging.configure.deep_scan_payload import build_deep_scan_payload
from packaging.configure.staging.review_confirmation import reconcile_reviewed_scan_with_platform_confirmation
from packaging.configure.staging.source_boundary import filter_generic_payload_items

DEFAULT_REVIEWED_SCAN_FILENAME = "reviewed-scan.json"


def _copy_dict_list(items: object) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [dict(item) for item in items if isinstance(item, dict)]


def build_review_binding(
    *,
    raw_scan: dict[str, Any],
    staging_root: str | Path,
    env_id: str,
    agent_type: str,
) -> dict[str, str]:
    return {
        "raw_scan_digest": compute_scan_digest(raw_scan),
        "staging_digest": compute_staging_digest(staging_root),
        "scan_only_digest": compute_scan_only_digest(staging_root),
        "env_id": str(env_id or "").strip(),
        "agent_type": str(agent_type or "").strip(),
    }


class _DigestBuilder:
    raw_scan = staticmethod(compute_scan_digest)
    staging = staticmethod(compute_staging_digest)
    scan_only = staticmethod(compute_scan_only_digest)


def reviewed_scan_matches_context(
    payload: dict[str, Any] | object,
    *,
    review_binding: dict[str, str] | None = None,
    raw_scan: dict[str, Any] | None = None,
    staging_root: str | Path | None = None,
    env_id: str | None = None,
    agent_type: str | None = None,
) -> bool:
    return _contract_reviewed_scan_matches_context(
        payload,
        review_binding=review_binding,
        raw_scan=raw_scan,
        staging_root=staging_root,
        env_id=env_id,
        agent_type=agent_type,
        digest_builder=_DigestBuilder,
    )


def refresh_reviewed_scan_metadata(
    payload: dict[str, Any] | object,
    *,
    review_binding: dict[str, str] | None = None,
    raw_scan: dict[str, Any] | None = None,
    staging_root: str | Path | None = None,
    env_id: str | None = None,
    agent_type: str | None = None,
) -> dict[str, Any] | object:
    if not isinstance(payload, dict) or not is_reviewed_scan_payload(payload):
        return payload

    existing_metadata = payload.get(REVIEW_METADATA_KEY)
    if not isinstance(existing_metadata, dict):
        return payload

    resolved_binding = _contract_resolved_review_binding(
        review_binding=review_binding,
        raw_scan=raw_scan,
        staging_root=staging_root,
        env_id=env_id,
        agent_type=agent_type,
        digest_builder=_DigestBuilder,
    )
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


def _generic_payload(payload: dict[str, Any], *, staging_root: str | Path, agent_type: str) -> list[Any]:
    resolved_agent_type = str(agent_type or "").strip()
    if not resolved_agent_type:
        raise ValueError("reviewed scan source filtering requires agent_type")
    excludes = _list_payload(payload, "excludes")
    excluded_relpaths = (
        str(item.get("source", "") or item.get("path", "")).strip()
        for item in excludes
        if isinstance(item, dict)
    )
    return filter_generic_payload_items(
        _list_payload(payload, "generic"),
        staging_root=staging_root,
        excluded_relpaths=excluded_relpaths,
        agent_type=resolved_agent_type,
    )


def build_reviewed_scan_from_scan(
    raw_scan: dict[str, Any],
    *,
    review_binding: dict[str, str],
    staging_root: str | Path,
) -> dict[str, Any]:
    excludes = _list_payload(raw_scan, "excludes")
    agent_type = str(review_binding.get("agent_type", "")).strip()
    if not agent_type:
        raise ValueError("review_binding.agent_type is required")
    reviewed_scan = {
        "url_proxy": _list_payload(raw_scan, "url_proxy"),
        "generic": _generic_payload(raw_scan, staging_root=staging_root, agent_type=agent_type),
        "env_var": _list_payload(raw_scan, "env_var"),
        "excludes": excludes,
        REVIEW_METADATA_KEY: _review_metadata_template(review_binding),
    }
    return reviewed_scan


__all__ = [
    "build_review_binding",
    "build_deep_scan_payload",
    "build_reviewed_scan_from_scan",
    "compute_scan_only_digest",
    "compute_scan_digest",
    "compute_staging_digest",
    "is_reviewed_scan_payload",
    "reconcile_reviewed_scan_with_platform_confirmation",
    "refresh_reviewed_scan_metadata",
    "reviewed_scan_matches_context",
    "sanitize_reviewed_scan_payload",
]
