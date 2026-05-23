from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from packaging._shared.common.fs import (
    display_stage_path,
    looks_like_absolute_symlink,
    looks_like_virtualenv_dir,
    record_skip,
)
from packaging._shared.common.packaged_files import (
    matches_workspace_allowlist,
    should_skip_packaged_path,
)
from packaging.configure.exclusion.stage import should_skip_high_risk_stage_file
from packaging.configure.staging.selection_filters import matches_selected_plugin_paths, matches_selected_skill_paths
from packaging.configure.staging.markdown_references import stage_direct_markdown_file_references
from packaging.configure.staging.tree_copy import copy_tree


@dataclass(frozen=True)
class StageTreeCopyRequest:

    source_root: Path
    target_root: Path
    display_prefix: str
    skip_skill_runtime_outputs: bool = False
    skill_runtime_prefixes: tuple[str, ...] = ()
    excluded_relpath_prefixes: tuple[str, ...] = ()
    selected_paths: set[str] | None = None
    selected_skill_paths: set[str] | None = None
    selected_plugin_paths: set[str] | None = None
    workspace_allowlist: set[str] | None = None
    apply_selection_filters: bool = True
    skip_high_risk_files: bool = True
    target: object = None
    stage_plan: object = None


@dataclass
class StageCopyState:

    skipped: list[str] = field(default_factory=list)
    skipped_seen: set[str] = field(default_factory=set)
    excluded_credential_files: set[str] = field(default_factory=set)


def _is_exact_allowlisted_file(
    display_path: str,
    workspace_allowlist: set[str] | None,
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
        skill_runtime_prefixes=request.skill_runtime_prefixes,
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
            skill_runtime_prefixes=request.skill_runtime_prefixes,
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
        if _is_exact_allowlisted_file(
            display_path,
            request.workspace_allowlist,
            is_dir=is_dir,
        ):
            return False
        if not request.apply_selection_filters:

            return bool(packaged_skip and not is_dir)
        if (
            not matches_selected_skill_paths(
                display_path,
                request.selected_paths,
                is_dir=is_dir,
                target=request.target,
            )
            or not matches_selected_plugin_paths(
                display_path,
                request.selected_plugin_paths,
                selected_skill_paths=request.selected_skill_paths,
                is_dir=is_dir,
                target=request.target,
            )
        ):
            return True
        if not is_dir:
            high_risk_skip = (
                request.skip_high_risk_files
                and should_skip_high_risk_stage_file(request.target, display_path)
            )
            if high_risk_skip:
                state.excluded_credential_files.add(display_path)
                return True
            if packaged_skip:
                if should_skip_high_risk_stage_file(request.target, display_path):
                    state.excluded_credential_files.add(display_path)
                return True
        return False

    one_hop_markdown_reference_files = 0

    def after_copy(source_file: Path, target_file: Path) -> None:
        nonlocal one_hop_markdown_reference_files
        one_hop_markdown_reference_files += stage_direct_markdown_file_references(
            source_file,
            target_file,
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
]
