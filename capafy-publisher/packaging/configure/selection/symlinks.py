from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from packaging._shared.contracts.stage_plan import StagePlan, StageTreeSource

from packaging._shared.contracts.selectable import (
    candidate_path_for_logical_path as _candidate_path_for_logical_path,
    normalize_display_prefix as _normalize_display_prefix,
)


@dataclass(frozen=True)
class SelectedSymlinkTreeSource:
    logical_path: str
    symlink_path: Path
    target_path: Path
    skip_skill_runtime_outputs: bool = False
    skill_runtime_prefixes: tuple[str, ...] = ()
    excluded_relpath_prefixes: tuple[str, ...] = ()


def _resolve_target_path(symlink_path: Path, *, logical_path: str) -> Path:
    try:
        target_path = symlink_path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError(f"Selected symlinked skill target does not exist: {logical_path} -> {symlink_path}") from exc
    if not target_path.is_dir():
        raise ValueError(f"Only directory symlink skills are currently supported: {logical_path} -> {target_path}")
    return target_path


def selected_symlink_tree_sources(
    tree_sources: list[StageTreeSource],
    selected_skill_paths: set[str] | None,
) -> list[SelectedSymlinkTreeSource]:
    if not selected_skill_paths:
        return []

    resolved_sources: list[SelectedSymlinkTreeSource] = []
    seen: set[str] = set()
    for logical_path in sorted(selected_skill_paths):
        matched_source: SelectedSymlinkTreeSource | None = None
        matched_prefix_length = -1
        for tree_source in tree_sources:
            source_root = tree_source.source_root.expanduser()
            candidate = _candidate_path_for_logical_path(
                source_root,
                tree_source.display_prefix,
                logical_path,
            )
            if candidate is None or not candidate.is_symlink():
                continue
            normalized_prefix = _normalize_display_prefix(tree_source.display_prefix)
            prefix_length = len(normalized_prefix)
            if prefix_length < matched_prefix_length:
                continue
            matched_prefix_length = prefix_length
            matched_source = SelectedSymlinkTreeSource(
                logical_path=logical_path,
                symlink_path=candidate,
                target_path=_resolve_target_path(candidate, logical_path=logical_path),
                skip_skill_runtime_outputs=tree_source.skip_skill_runtime_outputs,
                skill_runtime_prefixes=tree_source.skill_runtime_prefixes,
                excluded_relpath_prefixes=tree_source.excluded_relpath_prefixes,
            )
        if matched_source is None:
            continue
        if matched_source.logical_path in seen:
            continue
        seen.add(matched_source.logical_path)
        resolved_sources.append(matched_source)
    return resolved_sources


def augment_stage_plan_with_selected_symlinks(
    stage_plan: StagePlan,
    selected_skill_paths: set[str] | None,
) -> StagePlan:
    symlink_sources = selected_symlink_tree_sources(stage_plan.tree_sources, selected_skill_paths)
    if not symlink_sources:
        return stage_plan

    extra_tree_sources = [
        StageTreeSource(
            source_root=item.target_path,
            relative_target_root=Path(item.logical_path),
            display_prefix=item.logical_path,
            source_key=item.logical_path,
            source_value="dereferenced_symlink",
            skip_skill_runtime_outputs=item.skip_skill_runtime_outputs,
            skill_runtime_prefixes=item.skill_runtime_prefixes,
            excluded_relpath_prefixes=item.excluded_relpath_prefixes,
        )
        for item in symlink_sources
    ]
    return StagePlan(
        tree_sources=[*stage_plan.tree_sources, *extra_tree_sources],
        file_sources=stage_plan.file_sources,
        metadata=dict(stage_plan.metadata),
    )


__all__ = [
    "SelectedSymlinkTreeSource",
    "augment_stage_plan_with_selected_symlinks",
    "selected_symlink_tree_sources",
]
