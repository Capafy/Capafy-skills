from __future__ import annotations

from pathlib import Path, PurePosixPath

from datetime import datetime, timezone

from packaging._shared.common.fs import (
    looks_like_absolute_symlink,
    looks_like_virtualenv_dir,
)
from packaging._shared.common.packaged_files import (
    should_skip_packaged_path,
    should_skip_packaged_relpath,
)
from packaging.configure.staging.tree_copy import copy_tree
from packaging._shared.contracts.bundle_context import write_bundle_context
from packaging._shared.contracts.stage_manifest import write_stage_manifest
from packaging.configure.staging.review import compute_scan_only_digest, compute_staging_digest
from packaging._shared.contracts.path_shapes import unit_type_from_path
from packaging._shared.contracts.selection_groups import (
    is_selected_selection_group_item,
    normalize_documented_selection_groups,
)
from packaging._shared.contracts.selectable import candidate_path_for_logical_path
from packaging._shared.contracts.stage_plan import StagePlan
from packaging.configure.contexts import StageContext
from packaging._shared.runtimes.contracts import call_optional_target_hook


def _should_skip_buyout_relpath(relpath: str, *, is_dir: bool) -> bool:
    normalized = PurePosixPath(relpath.rstrip("/"))
    parts = [part.lower() for part in normalized.parts if part and part != "."]
    if should_skip_packaged_relpath(relpath, is_dir=is_dir):
        return True
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
        return _should_skip_buyout_relpath(relpath, is_dir=is_dir)

    return copy_tree(
        source_root,
        target_root,
        display_prefix,
        skipped,
        skipped_seen,
        should_skip=should_skip,
    )


def bundle_skill_name(selected_units: list[dict]) -> str:
    if len(selected_units) != 1:
        raise ValueError("buyout mode requires exactly one selected skill")
    return str(selected_units[0].get("name", "")).strip() or "buyout-skill"


def normalize_selected_units(
    bundle_context: dict,
    *,
    target=None,
) -> list[dict]:
    groups = normalize_documented_selection_groups(bundle_context.get("selection_groups"))
    normalized_units: list[dict] = []
    for item in groups.get("skills", []):
        if not is_selected_selection_group_item(item):
            continue
        path = str(item.get("path", "")).strip()
        if not path:
            continue
        unit_type = str(
            call_optional_target_hook(
                target,
                "infer_unit_type_from_path",
                path,
                default=unit_type_from_path(path, allow_bundle_units=True),
            )
            or ""
        ).strip()
        normalized_units.append(
            {
                "name": str(item.get("name", "")).strip() or PurePosixPath(path).name,
                "path": path,
                "unit_type": unit_type or "unknown",
            }
        )

    if len(normalized_units) != 1:
        raise ValueError("buyout mode requires exactly one selected skill")

    for item in normalized_units:
        unit_type = str(item.get("unit_type", "")).strip()
        if unit_type == "skill":
            continue

        raise ValueError(
            f"buyout only supports skill units, but received {unit_type or 'unknown'}: {item['path']}"
        )
    return normalized_units


def resolve_unit_source_path(unit_path: str, stage_plan: StagePlan) -> Path:
    matched_source: tuple[int, Path, str] | None = None
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
        raise ValueError(f"Selected buyout unit is not in the declared stage sources: {unit_path}")

    source_path = matched_source[1]
    if not source_path.exists():
        raise ValueError(f"Selected buyout unit source does not exist: {source_path}")
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
        target=target,
    )

    copied_files = 0
    skipped: list[str] = []
    skipped_seen: set[str] = set()
    included_units: list[dict] = []
    generated_files: list[str] = []
    bundle_skill_name(selected_units)

    unit = selected_units[0]
    source_path = resolve_unit_source_path(str(unit["path"]), stage_plan)
    if not source_path.is_dir():
        raise ValueError(f"buyout supports directory units only: {source_path}")
    copied_files += copy_unit_tree(
        source_path,
        staging_root,
        "",
        skipped,
        skipped_seen,
    )
    included_units.append(
        {
            "name": str(unit["name"]),
            "path": ".",
            "unit_type": str(unit["unit_type"]),
            "source_path": str(unit["path"]),
        }
    )

    bundle_context_payload = dict(bundle_context)

    bundle_context_path = write_bundle_context(staging_root, bundle_context_payload)
    stage_manifest_path = write_stage_manifest(
        staging_root,
        scan_only_prefixes=(),
        scan_only_source_map={},
        staging_digest=compute_staging_digest(staging_root),
        scan_only_digest=compute_scan_only_digest(staging_root),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    generated_files_payload = [bundle_context_path.name, *generated_files]

    payload = {
        "agent_type": "download",
        "staging_path": str(staging_root),
        "copied_files": copied_files,
        "skipped": skipped,
        "generated_files": generated_files_payload,
        "bundle_context_path": str(bundle_context_path),
        "stage_manifest_path": str(stage_manifest_path),
        "included_units": included_units,
        "selected_units": selected_units,
    }
    return payload


__all__ = [
    "bundle_skill_name",
    "copy_unit_tree",
    "normalize_selected_units",
    "resolve_unit_source_path",
    "stage_buyout",
]
