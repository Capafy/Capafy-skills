from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

from packaging._shared.contracts.selection_groups import (
    is_selected_selection_group_item,
    normalize_documented_selection_groups,
)
from packaging._shared.contracts.selectable import normalize_text
from packaging._shared.contracts.stage_plan import StagePlan


@dataclass(frozen=True)
class LocalReferenceConfirmation:
    has_explicit_selection_groups: bool
    selected_workspace_documents: frozenset[str]
    excluded_workspace_documents: frozenset[str]


def normalize_local_ref_path(path: object) -> str:
    normalized = normalize_text(path).replace("\\", "/").strip().strip("/")
    if not normalized:
        return ""
    return PurePosixPath(normalized).as_posix()


def _workspace_document_paths(items: Iterable[object], *, selected: bool) -> frozenset[str]:
    paths: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        if is_selected_selection_group_item(item) != selected:
            continue
        path = normalize_local_ref_path(item.get("path"))
        if path:
            paths.add(path)
    return frozenset(paths)


def local_reference_confirmation_from_stage_plan(stage_plan: StagePlan | None) -> LocalReferenceConfirmation:
    if stage_plan is None:
        return LocalReferenceConfirmation(False, frozenset(), frozenset())
    metadata = getattr(stage_plan, "metadata", {})
    has_explicit_selection = bool(
        isinstance(metadata, dict) and metadata.get("has_explicit_selection_groups")
    )
    if not has_explicit_selection:
        return LocalReferenceConfirmation(False, frozenset(), frozenset())
    raw_groups = metadata.get("selection_groups", {}) if isinstance(metadata, dict) else {}
    groups = normalize_documented_selection_groups(raw_groups)
    workspace_documents = groups.get("workspace_documents", [])
    return LocalReferenceConfirmation(
        True,
        _workspace_document_paths(workspace_documents, selected=True),
        _workspace_document_paths(workspace_documents, selected=False),
    )


def _append_variant(variants: set[str], prefix: str, relpath: PurePosixPath) -> None:
    normalized_prefix = normalize_local_ref_path(prefix)
    normalized_relpath = normalize_local_ref_path(relpath.as_posix())
    if not normalized_prefix:
        return
    if not normalized_relpath:
        variants.add(normalized_prefix)
        return
    variants.add(f"{normalized_prefix.rstrip('/')}/{normalized_relpath}")


def _path_relative_to(path: Path, root: Path) -> PurePosixPath | None:
    try:
        relpath = path.expanduser().resolve(strict=False).relative_to(root.expanduser().resolve(strict=False))
    except (OSError, ValueError):
        return None
    return PurePosixPath(relpath.as_posix())


def _stage_plan_path_variants(source_path: Path, stage_plan: StagePlan | None) -> set[str]:
    variants: set[str] = set()
    if stage_plan is None:
        return variants

    for file_source in getattr(stage_plan, "file_sources", []):
        source_file = Path(getattr(file_source, "source_file", Path(""))).expanduser()
        relpath = _path_relative_to(source_path, source_file.parent)
        if relpath is None:
            continue
        target_parent = PurePosixPath(getattr(file_source, "relative_target_path", Path("")).parent.as_posix())
        variants.add(normalize_local_ref_path((target_parent / relpath).as_posix()))

    for tree_source in getattr(stage_plan, "tree_sources", []):
        source_root = Path(getattr(tree_source, "source_root", Path(""))).expanduser()
        relpath = _path_relative_to(source_path, source_root)
        if relpath is None:
            continue
        for prefix in (
            str(getattr(tree_source, "display_prefix", "") or ""),
            str(getattr(tree_source, "relative_target_root", "") or ""),
        ):
            _append_variant(variants, prefix, relpath)

    return {variant for variant in variants if variant}


def _root_path_variants(source_path: Path, stage_plan: StagePlan | None) -> set[str]:
    variants: set[str] = set()
    roots: list[tuple[str, Path]] = [
        (".codex", Path.home() / ".codex"),
        (".config", Path.home() / ".config"),
        (".claude", Path.home() / ".claude"),
        (".agents", Path.home() / ".agents"),
        ("~", Path.home()),
    ]
    runtime_dir = ""
    if stage_plan is not None and isinstance(getattr(stage_plan, "metadata", {}), dict):
        runtime_dir = str(stage_plan.metadata.get("runtime_dir", "") or "").strip()
    if runtime_dir:
        runtime_root = Path(runtime_dir).expanduser()
        roots.extend(
            [
                ("~", runtime_root),
                ("workspace", runtime_root),
            ]
        )

    for prefix, root in roots:
        relpath = _path_relative_to(source_path, root)
        if relpath is not None:
            _append_variant(variants, prefix, relpath)
    return variants


def logical_variants_for_local_reference(source_path: Path, stage_plan: StagePlan | None) -> frozenset[str]:
    variants = _stage_plan_path_variants(source_path, stage_plan) | _root_path_variants(source_path, stage_plan)
    return frozenset(variant for variant in variants if variant)


def display_path_for_local_reference(source_path: Path, stage_plan: StagePlan | None) -> str:
    preferred_prefixes = (
        ".codex/",
        ".config/",
        ".claude/",
        ".agents/",
        "workspace/",
        "~/",
    )
    variants = sorted(
        logical_variants_for_local_reference(source_path, stage_plan),
        key=lambda item: (
            next((index for index, prefix in enumerate(preferred_prefixes) if item.startswith(prefix)), len(preferred_prefixes)),
            len(item),
            item,
        ),
    )
    if variants:
        return variants[0]
    try:
        return source_path.expanduser().resolve(strict=False).as_posix()
    except OSError:
        return source_path.expanduser().as_posix()


def local_reference_should_be_staged(source_path: Path, stage_plan: StagePlan | None) -> bool:
    confirmation = local_reference_confirmation_from_stage_plan(stage_plan)
    if not confirmation.has_explicit_selection_groups:
        return True
    variants = logical_variants_for_local_reference(source_path, stage_plan)
    if variants & confirmation.excluded_workspace_documents:
        return False
    return bool(variants & confirmation.selected_workspace_documents)


__all__ = [
    "LocalReferenceConfirmation",
    "display_path_for_local_reference",
    "local_reference_confirmation_from_stage_plan",
    "local_reference_should_be_staged",
    "logical_variants_for_local_reference",
    "normalize_local_ref_path",
]
