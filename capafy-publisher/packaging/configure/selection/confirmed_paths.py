from __future__ import annotations

import re
from pathlib import Path, PurePosixPath


def slugify_source_name(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-._").lower()
    return slug or "source"


def dedupe_packaged_base(base: PurePosixPath | Path, used: set[str]) -> PurePosixPath:
    candidate = PurePosixPath(base.as_posix())
    index = 2
    while candidate.as_posix() in used:
        candidate = PurePosixPath(f"{base.as_posix()}-{index}")
        index += 1
    used.add(candidate.as_posix())
    return candidate


def packaged_fallback_path(
    logical_path: str,
    source_path: Path,
    *,
    used_paths: set[str],
) -> str:
    category_dir = "workspace_documents"
    normalized = PurePosixPath(str(logical_path or "").rstrip("/")).as_posix()
    source_name = source_path.name or PurePosixPath(normalized).name or category_dir
    if source_path.is_file():
        base = PurePosixPath(category_dir) / source_name
        return dedupe_packaged_base(base, used_paths).as_posix()
    base = PurePosixPath(category_dir) / slugify_source_name(source_name)
    return dedupe_packaged_base(base, used_paths).as_posix()


__all__ = [
    "dedupe_packaged_base",
    "packaged_fallback_path",
    "slugify_source_name",
]
