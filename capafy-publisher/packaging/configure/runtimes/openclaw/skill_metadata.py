from __future__ import annotations

import re
from pathlib import Path

from packaging._shared.common.text_parse import strip_inline_comment, strip_wrapping_quotes
from packaging.configure.selection.markdown import read_markdown_text, split_frontmatter


_FRONTMATTER_NAME_PATTERN = re.compile(r"(?im)^name:\s*(.+?)\s*$")
_FRONTMATTER_OPENCLAW_SKILL_KEY_PATTERN = re.compile(r"(?im)^skillKey:\s*(.+?)\s*$")
_OPENCLAW_SKILL_KEY_PATH = ("metadata", "openclaw", "skillKey")


def runtime_skill_name_from_entry(item: dict) -> str:
    synopsis = str(item.get("synopsis", "")).strip()
    if synopsis.startswith("---"):
        lines = synopsis.splitlines()
        for line in lines[1:]:
            stripped = line.strip()
            if stripped == "---":
                break
            match = _FRONTMATTER_NAME_PATTERN.match(stripped)
            if not match:
                continue
            candidate = match.group(1).strip().strip("\"'")
            if candidate:
                return candidate
    return str(item.get("name", "")).strip()


def runtime_skill_key_from_entry(item: dict) -> str:
    skill_key = str(item.get("skill_key", "")).strip()
    if skill_key:
        return skill_key

    synopsis = str(item.get("synopsis", "")).strip()
    if synopsis.startswith("---"):
        lines = synopsis.splitlines()
        for line in lines[1:]:
            stripped = line.strip()
            if stripped == "---":
                break
            match = _FRONTMATTER_OPENCLAW_SKILL_KEY_PATTERN.match(stripped)
            if not match:
                continue
            candidate = match.group(1).strip().strip("\"'")
            if candidate:
                return candidate
    return runtime_skill_name_from_entry(item)


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
    doc_path = skill_dir / "SKILL.md"
    text = read_markdown_text(doc_path)
    if not text:
        return ""
    _metadata, body = split_frontmatter(text)
    raw_frontmatter = text[: len(text) - len(body)]
    return extract_frontmatter_nested_scalar(raw_frontmatter, _OPENCLAW_SKILL_KEY_PATH)


__all__ = [
    "extract_frontmatter_nested_scalar",
    "openclaw_skill_key_from_skill_dir",
    "runtime_skill_key_from_entry",
    "runtime_skill_name_from_entry",
]
