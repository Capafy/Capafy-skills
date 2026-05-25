from __future__ import annotations

from packaging._shared.contracts.path_shapes import (
    basic_owning_selectable_paths,
    extract_skill_dir_display_path,
)
from packaging._shared.runtimes.contracts import call_optional_target_hook


def infer_selection_unit_type(path: str, *, target=None) -> str:
    normalized = str(path or "").strip().rstrip("/")
    return str(
        call_optional_target_hook(
            target,
            "infer_unit_type_from_path",
            normalized,
            default="skill" if extract_skill_dir_display_path(normalized) else "unknown",
        )
        or ""
    ).strip()


def owning_selectable_paths(display_path: str, *, target=None) -> tuple[str, ...]:
    normalized = str(display_path or "").strip().rstrip("/")
    return tuple(
        str(path).strip().rstrip("/")
        for path in call_optional_target_hook(
            target,
            "owning_selectable_paths",
            normalized,
            default=basic_owning_selectable_paths(normalized),
        )
    )


def is_skill_selection_unit(path: str, *, target=None) -> bool:
    return infer_selection_unit_type(path, target=target) == "skill"


def has_skill_owning_path(display_path: str, *, target=None) -> bool:
    return any(
        path and is_skill_selection_unit(path, target=target)
        for path in owning_selectable_paths(display_path, target=target)
    )


__all__ = [
    "has_skill_owning_path",
    "infer_selection_unit_type",
    "is_skill_selection_unit",
    "owning_selectable_paths",
]
