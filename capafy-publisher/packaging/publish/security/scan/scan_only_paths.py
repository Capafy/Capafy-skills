from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

def is_scan_only_source_path(relpath: str) -> bool:
    normalized = str(relpath or "").strip().replace("\\", "/").lstrip("./").rstrip("/")
    return normalized == "_scan_only" or normalized.startswith("_scan_only/")


def normalize_scan_only_relpath(relpath: str, *, target: Any) -> str:
    normalized = PurePosixPath(str(relpath or "").strip() or ".").as_posix()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    if not normalized.startswith("_scan_only/"):
        return relpath
    profile = getattr(target, "profile", None)
    if not isinstance(profile, dict):
        return relpath
    fixed_scan_files = profile.get("fixed_scan_files", [])
    if not isinstance(fixed_scan_files, list):
        return relpath
    remainder = PurePosixPath(normalized[len("_scan_only/") :]).as_posix()
    if remainder.startswith("./"):
        remainder = remainder[2:]
    logical_paths = {
        _normalize_display_path(spec.get("display_path", ""))
        for spec in fixed_scan_files
        if isinstance(spec, dict) and str(spec.get("display_path", "")).strip()
    }
    if remainder in logical_paths:
        return remainder
    return relpath


def _normalize_display_path(value: object) -> str:
    normalized = PurePosixPath(str(value or "").strip()).as_posix()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


__all__ = ["is_scan_only_source_path", "normalize_scan_only_relpath"]
