from __future__ import annotations

from pathlib import Path
from typing import Optional

from packaging.publish.selection.markdown import (
    parse_markdown_description,
    parse_markdown_name,
    parse_markdown_synopsis,
)
from packaging.publish.selection.path_shapes import (
    basic_owning_selectable_paths,
    classify_basic_selectable_directory,
    extract_skill_dir_display_path,
)
from packaging.publish.selection.selectable import normalize_text
from packaging.runtime.contracts import call_optional_target_hook


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


def primary_instruction_doc(unit_path: Path, unit_type: str) -> Optional[Path]:
    if unit_type == "skill":
        candidate = unit_path / "SKILL.md"
        return candidate if candidate.is_file() else None
    return None


def missing_primary_doc_reason(unit_type: str) -> Optional[str]:
    return "missing SKILL.md" if unit_type == "skill" else None


def selectable_unit_name(unit_path: Path, unit_type: str, *, target=None) -> str:
    target_name = call_optional_target_hook(
        target,
        "selectable_unit_name",
        unit_path,
        unit_type,
        default=None,
    )
    if target_name:
        return target_name
    primary_doc = primary_instruction_doc(unit_path, unit_type)
    if primary_doc is not None:
        frontmatter_name = parse_markdown_name(primary_doc)
        if frontmatter_name:
            return frontmatter_name
    return unit_path.name


def selectable_unit_synopsis(unit_path: Path, unit_type: str) -> str:
    primary_doc = primary_instruction_doc(unit_path, unit_type)
    return parse_markdown_synopsis(primary_doc, max_lines=6, max_chars=400) if primary_doc else ""


def selectable_unit_description(unit_path: Path, unit_type: str) -> str:
    primary_doc = primary_instruction_doc(unit_path, unit_type)
    return parse_markdown_description(primary_doc) if primary_doc else ""


def classify_selectable_directory(target, unit_path: Path, display_path: str) -> tuple[Optional[str], str, bool]:
    return call_optional_target_hook(
        target,
        "classify_selectable_directory",
        unit_path,
        display_path,
        default=classify_basic_selectable_directory(unit_path, display_path),
    )


def finalize_selectable_entry(target, entry: dict, *, unit_path: Path) -> dict:
    return call_optional_target_hook(
        target,
        "finalize_selectable_entry",
        entry,
        unit_path=unit_path,
        default=entry,
    )


def resolve_workspace_root(
    *,
    workspace: Optional[str],
    target: Optional[object] = None,
) -> Optional[Path]:
    normalized_workspace = normalize_text(workspace)
    if not normalized_workspace:
        return None
    resolved = call_optional_target_hook(
        target,
        "resolve_workspace_reference",
        normalized_workspace,
        default=None,
    )
    if resolved is not None:
        return resolved
    fallback = Path(normalized_workspace).expanduser()
    if not fallback.is_dir():
        return None
    return fallback.resolve(strict=False)


__all__ = [
    "classify_selectable_directory",
    "finalize_selectable_entry",
    "has_skill_owning_path",
    "infer_selection_unit_type",
    "is_skill_selection_unit",
    "missing_primary_doc_reason",
    "owning_selectable_paths",
    "primary_instruction_doc",
    "resolve_workspace_root",
    "selectable_unit_description",
    "selectable_unit_name",
    "selectable_unit_synopsis",
]
