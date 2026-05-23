from __future__ import annotations

from pathlib import Path

from packaging._shared.runtimes.contracts import call_optional_target_hook
from packaging.configure.selection.markdown import (
    parse_markdown_description,
    parse_markdown_name,
    parse_markdown_synopsis,
)


def primary_instruction_doc(unit_path: Path, unit_type: str, *, target=None) -> Path | None:
    target_doc = call_optional_target_hook(
        target,
        "primary_instruction_doc",
        unit_path,
        unit_type,
        default=None,
    )
    if target_doc is not None:
        return target_doc
    if unit_type == "bundle_command":
        return unit_path if unit_path.is_file() else None
    if unit_type == "plugin":
        if unit_path.is_file():
            return unit_path
        for filename in ("README.md", "plugin.json", "package.json"):
            candidate = unit_path / filename
            if candidate.is_file():
                return candidate
        candidate = unit_path / ".claude-plugin" / "plugin.json"
        return candidate if candidate.is_file() else None
    if unit_type == "skill":
        candidate = unit_path / "SKILL.md"
        return candidate if candidate.is_file() else None
    if unit_type == "bundle_hook_pack":
        candidate = unit_path / "HOOK.md"
        return candidate if candidate.is_file() else None
    return None


def missing_primary_doc_reason(unit_type: str) -> str | None:
    if unit_type == "skill":
        return "missing SKILL.md"
    if unit_type == "bundle_hook_pack":
        return "missing HOOK.md"
    return None


def selectable_unit_name(unit_path: Path, unit_type: str, *, target=None) -> str:
    primary_doc = primary_instruction_doc(unit_path, unit_type, target=target)
    if primary_doc is not None:
        frontmatter_name = parse_markdown_name(primary_doc)
        if frontmatter_name:
            return frontmatter_name
    if unit_type == "bundle_command":
        return unit_path.stem
    if unit_type == "plugin" and unit_path.is_file():
        return unit_path.stem
    return unit_path.name


def instruction_synopsis(doc_path: Path) -> str:
    return parse_markdown_synopsis(doc_path, max_lines=6, max_chars=400)


def selectable_unit_synopsis(
    unit_path: Path,
    unit_type: str,
    *,
    target=None,
) -> str:
    primary_doc = primary_instruction_doc(unit_path, unit_type, target=target)
    if primary_doc is None:
        return ""
    return instruction_synopsis(primary_doc)


def selectable_unit_description(unit_path: Path, unit_type: str, *, target=None) -> str:
    primary_doc = primary_instruction_doc(unit_path, unit_type, target=target)
    if primary_doc is None:
        return ""
    return parse_markdown_description(primary_doc)
