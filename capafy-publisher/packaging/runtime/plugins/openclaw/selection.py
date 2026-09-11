from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Pattern

from packaging.common.text_parse import strip_inline_comment, strip_wrapping_quotes
from packaging.publish.selection.selection_groups import (
    SELECTION_GROUP_KEYS,
    normalize_documented_selection_groups,
)
from packaging.publish.selection.selectable import (
    has_parent_reference_path,
    is_absolute_like_path,
    normalize_text,
)
from packaging.publish.selection.markdown import read_markdown_text, split_frontmatter


_FRONTMATTER_NAME_PATTERN = re.compile(r"(?im)^name:\s*(.+?)\s*$")
_FRONTMATTER_OPENCLAW_SKILL_KEY_PATTERN = re.compile(r"(?im)^skillKey:\s*(.+?)\s*$")
_OPENCLAW_ROOT_PREFIX = ".openclaw"
_OPENCLAW_SKILL_KEY_PATH = ("metadata", "openclaw", "skillKey")
_OPENCLAW_WORKSPACE_PREFIX = PurePosixPath(".openclaw") / "workspace"


def _normalize_posix_path(value: object) -> str:
    text = normalize_text(value).replace("\\", "/").strip().strip("/")
    return PurePosixPath(text.rstrip("/")).as_posix() if text else ""


def canonicalize_openclaw_selection_path(path: object) -> str:
    normalized = _normalize_posix_path(path)
    if not normalized:
        return ""
    if is_absolute_like_path(normalized):
        raise ValueError(f"OpenClaw selection path must be logical, not absolute: {normalized}")
    if has_parent_reference_path(normalized):
        raise ValueError(f"OpenClaw selection path must not contain parent traversal: {normalized}")

    parts = PurePosixPath(normalized).parts
    if not parts:
        return ""
    if parts[0] == _OPENCLAW_ROOT_PREFIX:
        return normalized
    if parts[0] == "workspace" and len(parts) > 1:
        return (_OPENCLAW_WORKSPACE_PREFIX / PurePosixPath(*parts[1:])).as_posix()
    if parts[0] == "skills" and len(parts) > 1:
        return (_OPENCLAW_WORKSPACE_PREFIX / PurePosixPath(*parts)).as_posix()
    return normalized


def normalize_openclaw_selection_groups(raw_groups: object) -> dict[str, list[dict]]:
    groups = normalize_documented_selection_groups(raw_groups)
    normalized_groups: dict[str, list[dict]] = {key: [] for key in SELECTION_GROUP_KEYS}
    for key in SELECTION_GROUP_KEYS:
        for raw_item in groups.get(key, []):
            item = dict(raw_item)
            item_path = _normalize_posix_path(item.get("path"))
            if item_path:
                item["path"] = canonicalize_openclaw_selection_path(item_path)
            normalized_groups[key].append(item)
    return normalized_groups


def _runtime_frontmatter_value(item: dict, pattern: Pattern[str]) -> str:
    synopsis = str(item.get("synopsis", "")).strip()
    if not synopsis.startswith("---"):
        return ""
    for line in synopsis.splitlines()[1:]:
        stripped = line.strip()
        if stripped == "---":
            break
        match = pattern.match(stripped)
        if match:
            return match.group(1).strip().strip("\"'")
    return ""


def runtime_skill_name_from_entry(item: dict) -> str:
    return _runtime_frontmatter_value(item, _FRONTMATTER_NAME_PATTERN) or str(
        item.get("name", "")
    ).strip()


def runtime_skill_key_from_entry(item: dict) -> str:
    return (
        str(item.get("skill_key", "")).strip()
        or _runtime_frontmatter_value(item, _FRONTMATTER_OPENCLAW_SKILL_KEY_PATTERN)
        or runtime_skill_name_from_entry(item)
    )


def validate_openclaw_selected_skills(
    *,
    selected_paths: set[str],
    included_skills: list[dict],
) -> None:
    seen_skill_keys: dict[str, str] = {}

    for item in included_skills:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).strip()
        if path not in selected_paths:
            continue
        skill_key = runtime_skill_key_from_entry(item)
        if not skill_key:
            continue
        existing_path = seen_skill_keys.get(skill_key)
        if existing_path and existing_path != path:
            raise ValueError(
                "openclaw confirmed skills contain duplicate skill_key "
                f"{skill_key!r}: {existing_path!r} and {path!r}"
            )
        seen_skill_keys[skill_key] = path


def _leading_indent(line: str) -> int:
    return len(line.expandtabs(2)) - len(line.expandtabs(2).lstrip(" "))


def _expanded_key_path(stack_keys: list[str], key: str) -> tuple[str, ...]:
    parts: list[str] = []
    for item in [*stack_keys, key]:
        parts.extend(part for part in item.split(".") if part)
    return tuple(parts)


def extract_frontmatter_nested_scalar(raw: str, path: tuple[str, ...]) -> str:
    stack: list[tuple[int, str]] = []
    for line in str(raw or "").split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in line:
            continue

        key, _, remainder = line.partition(":")
        normalized_key = key.strip()
        indent = _leading_indent(line)
        while stack and indent <= stack[-1][0]:
            stack.pop()

        if _expanded_key_path([item[1] for item in stack], normalized_key) == path:
            value = remainder.strip()
            if value and value not in {">", "|"}:
                return strip_inline_comment(strip_wrapping_quotes(value))
            return ""

        value = remainder.strip()
        if not value or value in {">", "|"}:
            stack.append((indent, normalized_key))
    return ""


def openclaw_skill_key_from_skill_dir(skill_dir: Path) -> str:
    text = read_markdown_text(skill_dir / "SKILL.md")
    if not text:
        return ""
    _metadata, body = split_frontmatter(text)
    raw_frontmatter = text[: len(text) - len(body)]
    return extract_frontmatter_nested_scalar(raw_frontmatter, _OPENCLAW_SKILL_KEY_PATH)


__all__ = [
    "canonicalize_openclaw_selection_path",
    "extract_frontmatter_nested_scalar",
    "normalize_openclaw_selection_groups",
    "openclaw_skill_key_from_skill_dir",
    "runtime_skill_key_from_entry",
    "runtime_skill_name_from_entry",
    "validate_openclaw_selected_skills",
]
