from __future__ import annotations

from pathlib import PurePosixPath

from packaging._shared.contracts.selection_groups import (
    SELECTION_GROUP_KEYS,
    normalize_documented_selection_groups,
)
from packaging._shared.contracts.selectable import (
    has_parent_reference_path,
    is_absolute_like_path,
    normalize_text,
)


_OPENCLAW_ROOT_PREFIX = ".openclaw"
_OPENCLAW_WORKSPACE_PREFIX = PurePosixPath(".openclaw") / "workspace"


def _normalize_posix_path(value: object) -> str:
    text = normalize_text(value).replace("\\", "/").strip().strip("/")
    if not text:
        return ""
    return PurePosixPath(text.rstrip("/")).as_posix()


def canonicalize_openclaw_selection_path(path: object) -> str:
    normalized = _normalize_posix_path(path)
    if not normalized:
        return ""
    if is_absolute_like_path(normalized):
        raise ValueError(f"OpenClaw selection path must be logical, not absolute: {normalized}")
    if has_parent_reference_path(normalized):
        raise ValueError(f"OpenClaw selection path must not contain parent traversal: {normalized}")

    parts = PurePosixPath(normalized).parts
    if not parts:
        return ""
    if parts[0] == _OPENCLAW_ROOT_PREFIX:
        return normalized
    if parts[0] == "workspace" and len(parts) > 1:
        return (_OPENCLAW_WORKSPACE_PREFIX / PurePosixPath(*(str(part) for part in parts[1:]))).as_posix()
    if parts[0] == "skills" and len(parts) > 1:
        return (_OPENCLAW_WORKSPACE_PREFIX / PurePosixPath(*(str(part) for part in parts))).as_posix()
    if parts[0] == "extensions" and len(parts) > 1:
        return (PurePosixPath(_OPENCLAW_ROOT_PREFIX) / PurePosixPath(*parts)).as_posix()
    if parts[0] == "cron" and len(parts) > 1:
        return (PurePosixPath(_OPENCLAW_ROOT_PREFIX) / PurePosixPath(*parts)).as_posix()
    return normalized


def normalize_openclaw_selection_groups(raw_groups: object) -> dict[str, list[dict]]:
    groups = normalize_documented_selection_groups(raw_groups)
    normalized_groups: dict[str, list[dict]] = {key: [] for key in SELECTION_GROUP_KEYS}
    for key in SELECTION_GROUP_KEYS:
        for raw_item in groups.get(key, []):
            item = dict(raw_item)
            if key != "crons":
                item_path = _normalize_posix_path(item.get("path"))
                if item_path:
                    item["path"] = canonicalize_openclaw_selection_path(item_path)
            normalized_groups[key].append(item)
    return normalized_groups


__all__ = [
    "canonicalize_openclaw_selection_path",
    "normalize_openclaw_selection_groups",
]
