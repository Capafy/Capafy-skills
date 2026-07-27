from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Union

from packaging._shared.common.fs import safe_chmod
from packaging._shared.contracts.reviewed_scan import is_reviewed_scan_payload
from packaging._shared.reviewed_scan.digest import compute_scan_digest


logger = logging.getLogger(__name__)
REVIEWED_SCAN_FILENAME = "reviewed-scan.json"
SUBMITTED_CONFIG_REVIEWED_SCAN_FILENAME = "submitted-config-reviewed-scan.json"


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


def _submitted_config_reviewed_scan_path(developer_work_dir_path: Path) -> Path:
    return developer_work_dir_path / SUBMITTED_CONFIG_REVIEWED_SCAN_FILENAME


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


def _without_url_proxy_api_key_values(reviewed_scan: dict[str, Any]) -> dict[str, Any]:
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
        api_key = raw_entry.get("api_key")
        if isinstance(api_key, dict):
            entry["api_key"] = {**api_key, "value": ""}
        entries.append(entry)
    sanitized["url_proxy"] = entries
    return sanitized


def persist_reviewed_scan(
    reviewed_scan: dict[str, Any],
    *,
    developer_work_dir_path: Path,
) -> None:
    require_reviewed_scan_payload(reviewed_scan)
    reviewed_scan = _without_url_proxy_api_key_values(reviewed_scan)
    review_metadata = reviewed_scan.get("_review")
    if isinstance(review_metadata, dict):
        updated = dict(reviewed_scan)
        updated_metadata = dict(review_metadata)
        updated["_review"] = updated_metadata
        updated_metadata["reviewed_scan_digest"] = compute_scan_digest(updated)
        reviewed_scan = updated
    _write_private_json(developer_work_dir_path / REVIEWED_SCAN_FILENAME, reviewed_scan)


def persist_submitted_config_reviewed_scan(
    reviewed_scan: dict[str, Any],
    *,
    agent_version_id: str,
    developer_work_dir_path: Path,
) -> None:
    require_reviewed_scan_payload(reviewed_scan)
    reviewed_scan = _without_url_proxy_api_key_values(reviewed_scan)
    payload = {
        "agent_version_id": str(agent_version_id or "").strip(),
        "reviewed_scan_digest": compute_scan_digest(reviewed_scan),
        "reviewed_scan": reviewed_scan,
    }
    _write_private_json(_submitted_config_reviewed_scan_path(developer_work_dir_path), payload)


def read_reviewed_scan_file(reviewed_scan_path: str) -> dict[str, Any]:
    return _read_json_object(Path(reviewed_scan_path), label="reviewed-scan")


def read_submitted_config_reviewed_scan_file(
    *,
    developer_work_dir_path: Path,
    agent_version_id: str,
) -> dict[str, Any]:
    payload = _read_json_object(
        _submitted_config_reviewed_scan_path(developer_work_dir_path),
        label="submitted config reviewed-scan",
    )
    if not payload:
        return {}
    if str(payload.get("agent_version_id", "") or "").strip() != str(agent_version_id or "").strip():
        return {}
    reviewed_scan = payload.get("reviewed_scan")
    if not isinstance(reviewed_scan, dict) or not is_reviewed_scan_payload(reviewed_scan):
        return {}
    return reviewed_scan


__all__ = [
    "load_reviewed_scan_path",
    "persist_reviewed_scan",
    "persist_submitted_config_reviewed_scan",
    "read_reviewed_scan_file",
    "read_submitted_config_reviewed_scan_file",
    "require_reviewed_scan_payload",
]
