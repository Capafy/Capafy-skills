from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Optional

from packaging.common.fs import (
    looks_like_absolute_symlink,
    looks_like_virtualenv_dir,
)
from packaging.common.packaged_files import (
    should_skip_packaged_path,
)
from packaging.publish.staging.tree_copy import copy_tree
from packaging.publish.artifacts.bundle_context import write_bundle_context
from packaging.publish.staging.manifest import write_stage_manifest
from packaging.publish.selection.selection_groups import (
    is_selected_selection_group_item,
    normalize_documented_selection_groups,
)
from packaging.publish.selection.selectable import candidate_path_for_logical_path
from packaging.runtime.stage_plan import StagePlan
from packaging.publish.domain.contexts import StageContext
from packaging.publish.selection.confirmed_resolution import slugify_source_name
from packaging.publish.selection.units import infer_selection_unit_type


def _normalize_logical_path(value: object) -> str:
    normalized = str(value or "").strip().rstrip("/")
    return PurePosixPath(normalized).as_posix() if normalized else ""


def _should_skip_buyout_relpath(relpath: str) -> bool:
    normalized = PurePosixPath(relpath.rstrip("/"))
    parts = [part.lower() for part in normalized.parts if part and part != "."]
    if not parts:
        return False
    if parts[0] == "run":
        return True
    for index in range(len(parts) - 2):
        if parts[index] == "skills" and parts[index + 2] == "run":
            return True
    return False


def copy_unit_tree(
    source_root: Path,
    target_root: Path,
    display_prefix: str,
    skipped: list[str],
    skipped_seen: set[str],
) -> int:

    def should_skip(source_path: Path, relpath: str, is_dir: bool) -> bool:
        if is_dir and looks_like_virtualenv_dir(source_path):
            return True
        if looks_like_absolute_symlink(source_path):
            return True
        if should_skip_packaged_path(source_path, relpath, is_dir=is_dir):
            return True
        return _should_skip_buyout_relpath(relpath)

    return copy_tree(
        source_root,
        target_root,
        display_prefix,
        skipped,
        skipped_seen,
        should_skip=should_skip,
    )


def normalize_selected_units(
    bundle_context: dict,
    *,
    selected_skill_paths: Optional[set[str]] = None,
    target=None,
) -> list[dict]:
    groups = normalize_documented_selection_groups(bundle_context.get("selection_groups"))
    canonical_paths: Optional[set[str]] = None
    if selected_skill_paths is not None:
        canonical_paths = set()
        for raw_path in selected_skill_paths:
            path = _normalize_logical_path(raw_path)
            if path:
                canonical_paths.add(path)
    normalized_units: list[dict] = []
    seen_paths: set[str] = set()
    for item in groups.get("skills", []):
        if not is_selected_selection_group_item(item):
            continue
        path = _normalize_logical_path(item.get("path"))
        if not path:
            continue
        if canonical_paths is not None and path not in canonical_paths:
            continue
        if path in seen_paths:
            continue
        seen_paths.add(path)
        unit_type = infer_selection_unit_type(path, target=target)
        normalized_units.append(
            {
                "name": str(item.get("name", "")).strip() or PurePosixPath(path).name,
                "path": path,
                "unit_type": unit_type or "unknown",
            }
        )

    if canonical_paths is not None:
        missing_paths = sorted(canonical_paths - seen_paths)
        if missing_paths:
            raise ValueError(
                "download selected skill metadata is missing for: "
                + ", ".join(missing_paths)
            )

    if not normalized_units:
        raise ValueError("download mode requires at least one selected skill")

    for item in normalized_units:
        unit_type = str(item.get("unit_type", "")).strip()
        if unit_type == "skill":
            continue

        raise ValueError(
            f"download only supports skill units, but received {unit_type or 'unknown'}: {item['path']}"
        )
    return normalized_units


def resolve_unit_source_path(unit_path: str, stage_plan: StagePlan) -> Path:
    matched_source: Optional[tuple[int, Path, str]] = None
    for tree_source in stage_plan.tree_sources:
        candidate = candidate_path_for_logical_path(
            tree_source.source_root.expanduser(),
            tree_source.display_prefix,
            unit_path,
        )
        if candidate is None:
            continue
        display_prefix = tree_source.display_prefix.rstrip("/")
        if matched_source is None or len(display_prefix) > matched_source[0]:
            matched_source = (len(display_prefix), candidate, display_prefix)
    if matched_source is None:
        raise ValueError(f"Selected download unit is not in the declared stage sources: {unit_path}")

    source_path = matched_source[1]
    if not source_path.exists():
        raise ValueError(f"Selected download unit source does not exist: {source_path}")
    return source_path


def resolve_skill_source_path(unit_path: str, stage_plan: StagePlan) -> Path:
    source_path = resolve_unit_source_path(unit_path, stage_plan)
    if not source_path.is_dir():
        raise ValueError(f"download supports directory units only: {source_path}")
    if not (source_path / "SKILL.md").is_file():
        raise ValueError(f"selected download skill does not contain SKILL.md: {source_path}")
    return source_path


def stage_buyout(
    ctx: StageContext,
) -> dict:
    staging_root = ctx.staging_root
    stage_plan = ctx.stage_plan
    bundle_context = ctx.bundle_context
    target = ctx.target
    selected_units = normalize_selected_units(
        bundle_context,
        selected_skill_paths=ctx.selected_skill_paths,
        target=target,
    )

    copied_files = 0
    skipped: list[str] = []
    skipped_seen: set[str] = set()
    included_units: list[dict] = []
    used_skill_dirs: set[str] = set()
    for unit in selected_units:
        source_path = resolve_skill_source_path(str(unit["path"]), stage_plan)
        source_name = PurePosixPath(str(unit["path"])).name or str(unit["name"])
        base_skill_dir = slugify_source_name(source_name)
        skill_dir = base_skill_dir
        suffix = 2
        while skill_dir in used_skill_dirs:
            skill_dir = f"{base_skill_dir}-{suffix}"
            suffix += 1
        used_skill_dirs.add(skill_dir)

        copied_files += copy_unit_tree(
            source_path,
            staging_root / skill_dir,
            skill_dir,
            skipped,
            skipped_seen,
        )
        included_units.append(
            {
                "name": str(unit["name"]),
                "path": skill_dir,
                "unit_type": str(unit["unit_type"]),
                "source_path": str(unit["path"]),
            }
        )

    bundle_context_payload = dict(bundle_context)

    bundle_context_path = write_bundle_context(staging_root, bundle_context_payload)
    stage_manifest_path = write_stage_manifest(
        staging_root,
        scan_only_prefixes=(),
    )

    payload = {
        "agent_type": "download",
        "staging_path": str(staging_root),
        "copied_files": copied_files,
        "skipped": skipped,
        "generated_files": [bundle_context_path.name],
        "bundle_context_path": str(bundle_context_path),
        "stage_manifest_path": str(stage_manifest_path),
        "included_units": included_units,
        "selected_units": selected_units,
    }
    return payload


__all__ = [
    "copy_unit_tree",
    "normalize_selected_units",
    "resolve_skill_source_path",
    "resolve_unit_source_path",
    "stage_buyout",
]
