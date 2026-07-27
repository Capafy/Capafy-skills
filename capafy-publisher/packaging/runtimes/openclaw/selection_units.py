from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Optional

from packaging._shared.contracts.path_shapes import (
    basic_owning_selectable_paths,
    classify_basic_selectable_directory,
    extract_skill_dir_display_path,
)
from packaging.runtimes.openclaw.skill_metadata import openclaw_skill_key_from_skill_dir


def finalize_openclaw_selectable_entry(entry: dict, *, unit_path: Path) -> dict:
    if str(entry.get("unit_type", "skill")).strip() != "skill":
        return entry
    skill_key = openclaw_skill_key_from_skill_dir(unit_path)
    if not skill_key:
        return entry
    return {**entry, "skill_key": skill_key}


def classify_openclaw_directory_unit(
    unit_path: Path,
    display_path: str,
) -> tuple[Optional[str], str, bool]:
    return classify_basic_selectable_directory(unit_path, display_path)


def openclaw_owning_selectable_paths(display_path: str) -> tuple[str, ...]:
    return basic_owning_selectable_paths(display_path)


def infer_openclaw_unit_type_from_path(display_path: str) -> str:
    normalized = PurePosixPath(display_path.rstrip("/")).as_posix()
    if not normalized or normalized == ".":
        return "unknown"
    return "skill" if extract_skill_dir_display_path(normalized) else "unknown"


__all__ = [
    "classify_openclaw_directory_unit",
    "finalize_openclaw_selectable_entry",
    "infer_openclaw_unit_type_from_path",
    "openclaw_owning_selectable_paths",
]
