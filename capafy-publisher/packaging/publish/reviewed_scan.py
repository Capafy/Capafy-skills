from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Iterator, List, Mapping, Optional, TypedDict, Union

from packaging.common.fs import iter_workspace_files, relpath as fs_relpath, safe_chmod
from packaging.publish.staging.manifest import STAGE_MANIFEST_NAME

REVIEW_METADATA_KEY = "_review"
REVIEW_STATUS_REVIEWED = "reviewed"
REVIEW_BINDING_FIELDS = (
    "raw_scan_digest",
    "staging_digest",
    "env_id",
    "agent_type",
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
    url: ScanItem
    model: str
    api_format: str
    provider_name: str


class ReviewMetadata(TypedDict, total=False):
    reviewer: str
    status: str
    raw_scan_digest: str
    staging_digest: str
    env_id: str
    agent_type: str


class ScanGroups(TypedDict, total=False):
    url_proxy: List[UrlProxyEntry]
    generic: List[ScanItem]


class ReviewedScan(ScanGroups, total=False):
    _review: ReviewMetadata


def sanitize_reviewed_scan_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: payload[key]
        for key in ("url_proxy", "generic")
        if key in payload
    }


def credential_counts(scan_payload: dict) -> dict:
    counts: dict = {}
    for key in ("url_proxy", "generic"):
        value = scan_payload.get(key, [])
        counts[key] = len(value) if isinstance(value, list) else 0
    return counts


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


def _normalized_review_binding(review_binding: Optional[dict]) -> dict:
    resolved: dict = {}
    if isinstance(review_binding, dict):
        for field in REVIEW_BINDING_FIELDS:
            value = str(review_binding.get(field, "")).strip()
            if value:
                resolved[field] = value
    return resolved


def reviewed_scan_matches_context(
    payload: object,
    *,
    review_binding: dict,
) -> bool:
    if not is_reviewed_scan_payload(payload):
        return False
    metadata = payload[REVIEW_METADATA_KEY]  # type: ignore[index]

    expected = _normalized_review_binding(review_binding)

    for field, value in expected.items():
        if str(metadata.get(field, "")).strip() != value:
            return False
    return True


def reviewed_scan_context_diagnostics(
    payload: object,
    *,
    review_binding: Optional[dict] = None,
) -> dict[str, Any]:
    expected = _normalized_review_binding(review_binding)
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



def require_reviewed_scan_use(entry: Mapping[str, Any], *, label: str) -> str:
    raw_use = entry.get("use")
    if not isinstance(raw_use, str):
        raise ValueError(f"{label}.use must be a string")
    use = raw_use.strip()
    if not use:
        raise ValueError(f"{label}.use must not be empty for reviewed_scan")
    return use


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
    }
    metadata = payload.get(REVIEW_METADATA_KEY)
    if isinstance(metadata, dict):
        parsed[REVIEW_METADATA_KEY] = metadata
    return parsed


def validate_reviewed_scan_gate(reviewed_scan_payload: object, *, label: str = "reviewed_scan") -> None:
    _parse_reviewed_scan(reviewed_scan_payload, label=label)

def _stable_json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compute_scan_digest(scan: dict[str, Any]) -> str:
    normalized = sanitize_reviewed_scan_payload(scan)
    return hashlib.sha256(_stable_json_dumps(normalized).encode("utf-8")).hexdigest()


def _iter_digest_file_records(
    staging_root: Union[str, Path],
    *,
    include_scan_only: bool,
) -> Iterator[tuple[str, bytes]]:
    root = Path(staging_root)
    for path in sorted(iter_workspace_files(root, skip_system=False)):
        relpath = fs_relpath(path, root)
        normalized = relpath.strip("/")
        if normalized == STAGE_MANIFEST_NAME:
            continue
        is_scan_only = normalized == "_scan_only" or normalized.startswith("_scan_only/")
        if include_scan_only != is_scan_only:
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            raw = b""
        yield relpath, raw


def _compute_file_digest(staging_root: Union[str, Path], *, include_scan_only: bool) -> str:
    digest = hashlib.sha256()
    for relpath, raw in _iter_digest_file_records(staging_root, include_scan_only=include_scan_only):
        digest.update(relpath.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(raw).digest())
        digest.update(b"\0")
    return digest.hexdigest()


def compute_staging_digest(staging_root: Union[str, Path]) -> str:
    return _compute_file_digest(staging_root, include_scan_only=False)

REPLACE_WITH_PLACEHOLDER = "replace_with_placeholder"
EXCLUDE_VALUE = "exclude_value"


FINAL_DISPOSITIONS = (
    REPLACE_WITH_PLACEHOLDER,
    EXCLUDE_VALUE,
)


def iter_disposition_entries(reviewed_scan: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for bucket in ("url_proxy", "generic"):
        value = reviewed_scan.get(bucket, [])
        if not isinstance(value, list):
            continue
        for index, entry in enumerate(value):
            if not isinstance(entry, dict):
                continue
            yield {
                "bucket": bucket,
                "index": index,
                "entry": entry,
            }


def reviewed_scan_has_final_dispositions(reviewed_scan: dict[str, Any]) -> bool:
    for item in iter_disposition_entries(reviewed_scan):
        entry = item["entry"]
        disposition = str(entry.get("final_disposition", "")).strip()
        if disposition not in FINAL_DISPOSITIONS:
            return False
    return True


def _entry_primary_field(entry: dict[str, Any]) -> str:
    field = str(entry.get("field", "")).strip()
    if field:
        return field
    url = entry.get("url")
    if isinstance(url, dict):
        field = str(url.get("field", "")).strip()
        if field:
            return field
    return str(entry.get("use", "")).strip() or "unnamed_entry"


def _clone_with_final_disposition(entry: dict[str, Any], disposition: str) -> dict[str, Any]:
    updated = dict(entry)
    updated["final_disposition"] = disposition
    return updated


def apply_buyout_dispositions(
    reviewed_scan: dict[str, Any],
    *,
    overrides: dict[str, str],
) -> dict[str, Any]:
    updated = dict(reviewed_scan)
    for bucket in ("url_proxy", "generic"):
        if isinstance(updated.get(bucket), list):
            updated[bucket] = list(updated[bucket])
    field_to_override = {str(key).strip(): str(value).strip() for key, value in overrides.items() if str(key).strip()}
    for item in iter_disposition_entries(updated):
        entry = dict(item["entry"])
        field = _entry_primary_field(entry)
        override = field_to_override.get(field)
        if override:
            if override not in FINAL_DISPOSITIONS:
                raise ValueError(f"unknown disposition for {field}: {override}")
            entry = _clone_with_final_disposition(entry, override)
        updated[item["bucket"]][item["index"]] = entry
    return updated


def disposition_summary(reviewed_scan: dict[str, Any]) -> dict[str, int]:
    counts = {name: 0 for name in FINAL_DISPOSITIONS}
    missing = 0
    invalid = 0
    for item in iter_disposition_entries(reviewed_scan):
        entry = item["entry"]
        disposition = str(entry.get("final_disposition", "")).strip()
        if disposition in counts:
            counts[disposition] += 1
        elif disposition:
            invalid += 1
        else:
            missing += 1
    return {
        **counts,
        "missing": missing,
        "invalid": invalid,
        "total": sum(counts.values()) + missing + invalid,
    }

logger = logging.getLogger(__name__)
REVIEWED_SCAN_FILENAME = "reviewed-scan.json"


def require_reviewed_scan_payload(payload: Union[dict[str, Any], object]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("reviewed_scan_payload must be an object")
    if not is_reviewed_scan_payload(payload):
        raise ValueError(
            "reviewed_scan_payload must contain _review.reviewer, "
            "_review.status=reviewed, and matching review binding fields"
        )
    return payload


def load_reviewed_scan_path(*, developer_work_dir_path: Path) -> str:
    return str(developer_work_dir_path / REVIEWED_SCAN_FILENAME)


def _write_private_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_chmod(path.parent, 0o700)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    safe_chmod(path, 0o600)


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("failed to parse %s JSON at %s: %s", label, path, exc)
        return {}
    except OSError as exc:
        logger.warning("failed to read %s JSON at %s: %s", label, path, exc)
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _without_legacy_url_proxy_api_keys(reviewed_scan: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(reviewed_scan)
    raw_entries = reviewed_scan.get("url_proxy")
    if not isinstance(raw_entries, list):
        return sanitized
    entries: list[Any] = []
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            entries.append(raw_entry)
            continue
        entry = dict(raw_entry)
        entry.pop("api_key", None)
        entries.append(entry)
    sanitized["url_proxy"] = entries
    return sanitized


def persist_reviewed_scan(
    reviewed_scan: dict[str, Any],
    *,
    developer_work_dir_path: Path,
) -> None:
    require_reviewed_scan_payload(reviewed_scan)
    reviewed_scan = _without_legacy_url_proxy_api_keys(reviewed_scan)
    review_metadata = reviewed_scan.get("_review")
    if isinstance(review_metadata, dict):
        updated = dict(reviewed_scan)
        updated_metadata = dict(review_metadata)
        updated["_review"] = updated_metadata
        updated_metadata["reviewed_scan_digest"] = compute_scan_digest(updated)
        reviewed_scan = updated
    _write_private_json(developer_work_dir_path / REVIEWED_SCAN_FILENAME, reviewed_scan)


def read_reviewed_scan_file(reviewed_scan_path: str) -> dict[str, Any]:
    return _read_json_object(Path(reviewed_scan_path), label="reviewed-scan")

__all__ = [
    "REVIEW_BINDING_FIELDS",
    "REVIEW_METADATA_KEY",
    "REVIEW_STATUS_REVIEWED",
    "ReviewMetadata",
    "ReviewedScan",
    "ScanGroups",
    "ScanItem",
    "UrlProxyEntry",
    "EXCLUDE_VALUE",
    "FINAL_DISPOSITIONS",
    "REPLACE_WITH_PLACEHOLDER",
    "REVIEWED_SCAN_FILENAME",
    "apply_buyout_dispositions",
    "compute_scan_digest",
    "compute_staging_digest",
    "credential_counts",
    "disposition_summary",
    "is_reviewed_scan_payload",
    "iter_disposition_entries",
    "load_reviewed_scan_path",
    "persist_reviewed_scan",
    "read_reviewed_scan_file",
    "require_reviewed_scan_payload",
    "require_reviewed_scan_use",
    "required_list",
    "reviewed_scan_context_diagnostics",
    "reviewed_scan_has_final_dispositions",
    "reviewed_scan_matches_context",
    "sanitize_reviewed_scan_payload",
    "validate_reviewed_scan_gate",
]
