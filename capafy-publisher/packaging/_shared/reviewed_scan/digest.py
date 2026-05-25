from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterator, Union

from packaging._shared.common.fs import iter_workspace_files, relpath as fs_relpath
from packaging._shared.contracts.reviewed_scan import sanitize_reviewed_scan_payload
from packaging._shared.contracts.stage_manifest import STAGE_MANIFEST_NAME


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


def compute_scan_only_digest(staging_root: Union[str, Path]) -> str:
    return _compute_file_digest(staging_root, include_scan_only=True)


__all__ = [
    "compute_scan_digest",
    "compute_scan_only_digest",
    "compute_staging_digest",
]
