from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Union

from packaging._shared.common.fs import safe_chmod
from packaging._shared.contracts.reviewed_scan import is_reviewed_scan_payload
from packaging._shared.reviewed_scan.digest import compute_scan_digest


logger = logging.getLogger(__name__)


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
    return str(developer_work_dir_path / "reviewed-scan.json")


def persist_reviewed_scan(
    reviewed_scan: dict[str, Any],
    *,
    developer_work_dir_path: Path,
) -> None:
    require_reviewed_scan_payload(reviewed_scan)
    review_metadata = reviewed_scan.get("_review")
    if isinstance(review_metadata, dict):
        updated = dict(reviewed_scan)
        updated_metadata = dict(review_metadata)
        updated["_review"] = updated_metadata
        updated_metadata["reviewed_scan_digest"] = compute_scan_digest(updated)
        reviewed_scan = updated
    path = developer_work_dir_path / "reviewed-scan.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_chmod(path.parent, 0o700)
    path.write_text(json.dumps(reviewed_scan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    safe_chmod(path, 0o600)


def read_reviewed_scan_file(reviewed_scan_path: str) -> dict[str, Any]:
    path = Path(reviewed_scan_path)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("failed to parse reviewed-scan JSON at %s: %s", reviewed_scan_path, exc)
        return {}
    except OSError as exc:
        logger.warning("failed to read reviewed-scan JSON at %s: %s", reviewed_scan_path, exc)
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


__all__ = [
    "load_reviewed_scan_path",
    "persist_reviewed_scan",
    "read_reviewed_scan_file",
    "require_reviewed_scan_payload",
]
