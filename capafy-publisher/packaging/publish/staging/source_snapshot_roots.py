from __future__ import annotations

from pathlib import Path
from typing import Any

from packaging.common.packaged_files import is_publisher_source_path
from packaging.publish.selection.selectable import candidate_path_for_logical_path
from packaging.publish.selection.selection_groups import (
    is_selected_selection_group_item,
    normalize_documented_selection_groups,
)


def _selected_skill_source(logical_path: str, stage_plan: Any) -> Path:
    matches: list[tuple[int, Path]] = []
    for tree_source in stage_plan.tree_sources:
        candidate = candidate_path_for_logical_path(
            tree_source.source_root.expanduser(),
            tree_source.display_prefix,
            logical_path,
        )
        if candidate is not None and candidate.exists():
            matches.append((len(tree_source.display_prefix.rstrip("/")), candidate))
    if not matches:
        raise ValueError(f"selected skill source cannot be resolved: {logical_path}")
    return max(matches, key=lambda match: match[0])[1]


def _selected_document_source(logical_path: str, stage_plan: Any) -> Path:
    for file_source in stage_plan.file_sources:
        if str(file_source.source_value or "").strip() == logical_path:
            return file_source.source_file
    for tree_source in stage_plan.tree_sources:
        if str(tree_source.source_value or "").strip() == logical_path:
            return tree_source.source_root
    raise ValueError(f"selected workspace document source cannot be resolved: {logical_path}")


def build_publish_source_snapshot_roots(
    *,
    selection_groups: object,
    stage_plan: Any,
) -> tuple[dict[str, Any], ...]:
    groups = normalize_documented_selection_groups(selection_groups)
    roots: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for group_name, items in groups.items():
        for item in items:
            if not isinstance(item, dict) or not is_selected_selection_group_item(item):
                continue
            logical_path = str(item.get("path", "") or "").strip()
            if not logical_path:
                raise ValueError(f"selected {group_name} item is missing path")
            source = (
                _selected_skill_source(logical_path, stage_plan)
                if group_name == "skills"
                else _selected_document_source(logical_path, stage_plan)
            )
            source = source.resolve(strict=True)
            if is_publisher_source_path(source):
                raise ValueError(f"publisher source cannot be selected for snapshot: {logical_path}")
            identity = (group_name, logical_path, str(source))
            if identity in seen:
                continue
            roots.append(
                {
                    "group": group_name,
                    "logical_path": logical_path,
                    "source_path": str(source),
                }
            )
            seen.add(identity)
    return tuple(roots)


__all__ = ["build_publish_source_snapshot_roots"]
