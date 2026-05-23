from __future__ import annotations

from pathlib import PurePosixPath

from packaging._shared.runtimes.contracts import call_optional_target_hook

from packaging._shared.contracts.path_shapes import (
    basic_owning_plugin_paths,
    basic_owning_selectable_paths,
    is_plugin_unit_type,
    unit_type_from_path,
)


def looks_like_plugin_related_display_path(display_path: str, *, target=None) -> bool:
    normalized = _normalized_display_path(display_path)
    return bool(
        call_optional_target_hook(
            target,
            "looks_like_plugin_related_path",
            normalized,
            default=False,
        )
    )


def _normalized_display_path(display_path: str) -> str:
    return PurePosixPath(display_path.rstrip("/")).as_posix()


def _selectable_owning_paths(display_path: str, target=None) -> tuple[str, ...]:
    return tuple(
        call_optional_target_hook(
            target,
            "owning_selectable_paths",
            display_path,
            default=basic_owning_selectable_paths(display_path),
        )
    )


def _plugin_owning_paths(display_path: str, target=None) -> tuple[str, ...]:
    owning_paths = tuple(
        call_optional_target_hook(
            target,
            "owning_plugin_paths",
            display_path,
            default=basic_owning_plugin_paths(display_path),
        )
    )
    selectable_paths = tuple(
        call_optional_target_hook(
            target,
            "owning_selectable_paths",
            display_path,
            default=(),
        )
    )
    if owning_paths or not selectable_paths:
        return owning_paths
    return tuple(
        path
        for path in selectable_paths
        if is_plugin_unit_type(
            str(
                call_optional_target_hook(
                    target,
                    "infer_unit_type_from_path",
                    path,
                    default=unit_type_from_path(path),
                )
            ).strip()
        )
    )


def _matches_selected_paths(
    display_path: str,
    selected_paths: set[str],
    owning_paths: tuple[str, ...],
    *,
    is_dir: bool | None = None,
    selected_path_filter=None,
    match_descendants_for_files: bool = False,
) -> bool:
    def selected_path_allowed(path: str) -> bool:
        return selected_path_filter is None or selected_path_filter(path)

    if owning_paths:
        if any(path in selected_paths and selected_path_allowed(path) for path in owning_paths):
            return True

    if is_dir is False and not match_descendants_for_files:
        return False

    normalized = _normalized_display_path(display_path)
    if not normalized or normalized == ".":
        return True
    return any(
        selected_path.startswith(f"{normalized}/") and selected_path_allowed(selected_path)
        for selected_path in selected_paths
    )


def matches_selected_skill_paths(
    display_path: str,
    selected_skill_paths: set[str] | None,
    *,
    is_dir: bool | None = None,
    target=None,
) -> bool:
    if selected_skill_paths is None:
        return True
    return _matches_selected_paths(
        display_path,
        selected_skill_paths,
        _selectable_owning_paths(display_path, target),
        is_dir=is_dir,
    )


def matches_selected_plugin_paths(
    display_path: str,
    selected_plugin_paths: set[str] | None,
    *,
    selected_skill_paths: set[str] | None = None,
    is_dir: bool | None = None,
    target=None,
) -> bool:
    if selected_plugin_paths is None:
        return True
    if _matches_selected_non_plugin_unit_paths(
        display_path,
        selected_skill_paths,
        is_dir=is_dir,
        target=target,
    ):
        return True
    owning_paths = _plugin_owning_paths(display_path, target)
    if _matches_selected_paths(
        display_path,
        selected_plugin_paths,
        owning_paths,
        is_dir=is_dir,
        match_descendants_for_files=True,
    ):
        return True
    normalized = _normalized_display_path(display_path)
    if not owning_paths:
        return not looks_like_plugin_related_display_path(normalized, target=target)
    if is_dir is False:
        return False
    return False


def _matches_selected_non_plugin_unit_paths(
    display_path: str,
    selected_skill_paths: set[str] | None,
    *,
    is_dir: bool | None = None,
    target=None,
) -> bool:
    if not selected_skill_paths:
        return False
    return _matches_selected_paths(
        display_path,
        selected_skill_paths,
        _selectable_owning_paths(display_path, target),
        is_dir=is_dir,
        selected_path_filter=lambda path: _is_non_plugin_unit_path(path, target=target),
    )


def _is_non_plugin_unit_path(path: str, *, target=None) -> bool:
    unit_type = str(
        call_optional_target_hook(
            target,
            "infer_unit_type_from_path",
            path,
            default=unit_type_from_path(path),
        )
    ).strip()
    return not is_plugin_unit_type(unit_type)


__all__ = [
    "looks_like_plugin_related_display_path",
    "matches_selected_plugin_paths",
    "matches_selected_skill_paths",
]
