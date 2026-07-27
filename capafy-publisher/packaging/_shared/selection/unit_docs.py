from __future__ import annotations
from typing import Optional

from pathlib import Path

from packaging._shared.runtimes.contracts import call_optional_target_hook
from packaging._shared.selection.markdown import (
    parse_markdown_description,
    parse_markdown_name,
    parse_markdown_synopsis,
)


def primary_instruction_doc(unit_path: Path, unit_type: str, *, target=None) -> Optional[Path]:
    target_doc = call_optional_target_hook(
        target,
        "primary_instruction_doc",
        unit_path,
        unit_type,
        default=None,
    )
    if target_doc is not None:
        return target_doc
    if unit_type == "skill":
        candidate = unit_path / "SKILL.md"
        return candidate if candidate.is_file() else None
    return None


def missing_primary_doc_reason(unit_type: str) -> Optional[str]:
    if unit_type == "skill":
        return "missing SKILL.md"
    return None


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
    primary_doc = primary_instruction_doc(unit_path, unit_type, target=target)
    if primary_doc is not None:
        frontmatter_name = parse_markdown_name(primary_doc)
        if frontmatter_name:
            return frontmatter_name
    return unit_path.name


def selectable_unit_synopsis(
    unit_path: Path,
    unit_type: str,
    *,
    target=None,
) -> str:
    primary_doc = primary_instruction_doc(unit_path, unit_type, target=target)
    if primary_doc is None:
        return ""
    return parse_markdown_synopsis(primary_doc, max_lines=6, max_chars=400)


def selectable_unit_description(unit_path: Path, unit_type: str, *, target=None) -> str:
    primary_doc = primary_instruction_doc(unit_path, unit_type, target=target)
    if primary_doc is None:
        return ""
    return parse_markdown_description(primary_doc)
