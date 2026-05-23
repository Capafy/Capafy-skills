from __future__ import annotations

from pathlib import Path
from typing import Any

from packaging._shared.contracts.stage_plan import StageFileSource, StageTreeSource
from packaging._shared.contracts.selectable import is_absolute_like_path

def stage_sources_for_entry(entry: Any) -> tuple[StageTreeSource | None, StageFileSource | None]:
    if entry.source_kind == "directory":
        return (
            StageTreeSource(
                source_root=entry.source_path,
                relative_target_root=Path(entry.packaged_path),
                display_prefix=entry.logical_path,
                source_key=entry.packaged_path,
                source_value=entry.logical_path,
            ),
            None,
        )
    return (
        None,
        StageFileSource(
            source_file=entry.source_path,
            relative_target_path=Path(entry.packaged_path),
            source_key=entry.packaged_path,
            source_value=entry.logical_path,
        ),
    )


def manifest_item(entry: Any, *, preserve_logical_path: bool, packaged: bool) -> dict:
    source_path = entry.logical_path if preserve_logical_path or is_absolute_like_path(entry.logical_path) else str(entry.source_path)
    return {
        "source_path": source_path,
        "resolved_source_path": str(entry.source_path),
        "logical_path": entry.logical_path,
        "packaged_path": entry.packaged_path if packaged else "",
        "source_kind": entry.source_kind,
    }


__all__ = [
    "manifest_item",
    "stage_sources_for_entry",
]
