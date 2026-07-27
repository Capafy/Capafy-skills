from __future__ import annotations

from pathlib import PurePosixPath
from typing import Optional

from packaging._shared.selection.unit_types import owning_selectable_paths


def _normalized_display_path(display_path: str) -> str:
    return PurePosixPath(display_path.rstrip("/")).as_posix()


def _matches_selected_paths(
    display_path: str,
    selected_paths: set[str],
    owning_paths: tuple[str, ...],
    *,
    is_dir: Optional[bool] = None,
) -> bool:
    if owning_paths and any(path in selected_paths for path in owning_paths):
        return True
    if is_dir is False:
        return False
    normalized = _normalized_display_path(display_path)
    if not normalized or normalized == ".":
        return True
    return any(selected_path.startswith(f"{normalized}/") for selected_path in selected_paths)


def matches_selected_skill_paths(
    display_path: str,
    selected_skill_paths: Optional[set[str]],
    *,
    is_dir: Optional[bool] = None,
    target=None,
) -> bool:
    if selected_skill_paths is None:
        return True
    return _matches_selected_paths(
        display_path,
        selected_skill_paths,
        owning_selectable_paths(display_path, target=target),
        is_dir=is_dir,
    )


__all__ = ["matches_selected_skill_paths"]
