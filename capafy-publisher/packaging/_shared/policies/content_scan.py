from __future__ import annotations

from pathlib import PurePosixPath

from packaging._shared.common.constants import DEPENDENCY_MANIFEST_FILES


CONTENT_SCAN_EXCLUDED_FILES = frozenset(DEPENDENCY_MANIFEST_FILES)


def _basename(path: str) -> str:
    return PurePosixPath(str(path or "").replace("\\", "/")).name


def should_skip_content_scan_for_file(path: str) -> bool:
    return _basename(path) in CONTENT_SCAN_EXCLUDED_FILES


def should_skip_local_path_cleanup_for_file(path: str) -> bool:
    return _basename(path) in CONTENT_SCAN_EXCLUDED_FILES


__all__ = [
    "CONTENT_SCAN_EXCLUDED_FILES",
    "should_skip_content_scan_for_file",
    "should_skip_local_path_cleanup_for_file",
]
