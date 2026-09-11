from __future__ import annotations
from typing import Optional

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from packaging.common.fs import (
    display_stage_path,
    looks_like_absolute_symlink,
    looks_like_virtualenv_dir,
    record_skip,
)
from packaging.common.packaged_files import (
    matches_workspace_allowlist,
    should_skip_packaged_path,
)
from packaging.publish.selection.units import owning_selectable_paths
from packaging.publish.staging.exclusions import should_skip_high_risk_stage_file
from packaging.publish.staging.markdown_references import stage_direct_markdown_file_references
from packaging.publish.staging.tree_copy import copy_tree


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


@dataclass(frozen=True)
class StageTreeCopyRequest:

    source_root: Path
    target_root: Path
    staging_root: Path
    display_prefix: str
    skip_skill_runtime_outputs: bool = False
    excluded_relpath_prefixes: tuple[str, ...] = ()
    selected_paths: Optional[set[str]] = None
    workspace_allowlist: Optional[set[str]] = None
    apply_selection_filters: bool = True
    skip_high_risk_files: bool = True
    target: object = None
    stage_plan: object = None


@dataclass
class StageCopyState:

    skipped: list[str] = field(default_factory=list)
    skipped_seen: set[str] = field(default_factory=set)


def _is_exact_allowlisted_file(
    display_path: str,
    workspace_allowlist: Optional[set[str]],
    *,
    is_dir: bool,
) -> bool:
    if is_dir or workspace_allowlist is None:
        return False
    normalized = PurePosixPath(display_path.rstrip("/")).as_posix()
    return bool(normalized and normalized in workspace_allowlist)


def copy_stage_tree(
    request: StageTreeCopyRequest,
    state: StageCopyState,
) -> int:
    source_root = request.source_root
    target_root = request.target_root
    display_prefix = request.display_prefix
    if should_skip_packaged_path(
        source_root,
        source_root.name,
        is_dir=True,
        skip_skill_runtime_outputs=request.skip_skill_runtime_outputs,
        excluded_relpath_prefixes=request.excluded_relpath_prefixes,
    ):
        record_skip(state.skipped, state.skipped_seen, display_prefix, is_dir=True)
        return 0

    def should_skip(source_path: Path, relative_path: str, is_dir: bool) -> bool:
        display_path = display_stage_path(display_prefix, relative_path)
        if is_dir and looks_like_virtualenv_dir(source_path):
            return True
        if looks_like_absolute_symlink(source_path):
            return True
        packaged_skip = should_skip_packaged_path(
            source_path,
            relative_path,
            is_dir=is_dir,
            skip_skill_runtime_outputs=request.skip_skill_runtime_outputs,
            excluded_relpath_prefixes=request.excluded_relpath_prefixes,
        )
        if is_dir and packaged_skip:
            return True
        if not matches_workspace_allowlist(
            display_path,
            request.workspace_allowlist,
            is_dir=is_dir,
        ):
            return True
        if (
            not is_dir
            and request.skip_high_risk_files
            and should_skip_high_risk_stage_file(request.target, display_path)
        ):
            return True
        if _is_exact_allowlisted_file(
            display_path,
            request.workspace_allowlist,
            is_dir=is_dir,
        ):
            return False
        if not request.apply_selection_filters:

            return bool(packaged_skip and not is_dir)
        if not matches_selected_skill_paths(
            display_path,
            request.selected_paths,
            is_dir=is_dir,
            target=request.target,
        ):
            return True
        if not is_dir:
            if packaged_skip:
                return True
        return False

    one_hop_markdown_reference_files = 0

    def after_copy(source_file: Path, target_file: Path) -> None:
        nonlocal one_hop_markdown_reference_files
        one_hop_markdown_reference_files += stage_direct_markdown_file_references(
            source_file,
            target_file,
            staging_root=request.staging_root,
            target=request.target,
            stage_plan=request.stage_plan,
        )

    return copy_tree(
        source_root,
        target_root,
        display_prefix,
        state.skipped,
        state.skipped_seen,
        should_skip=should_skip,
        after_copy=after_copy,
    ) + one_hop_markdown_reference_files


__all__ = [
    "StageCopyState",
    "StageTreeCopyRequest",
    "copy_stage_tree",
    "matches_selected_skill_paths",
]
