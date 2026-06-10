from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from packaging._shared.common.text_parse import strip_inline_comment, strip_wrapping_quotes


_FRONTMATTER_DELIMITER = "---"
_SUPPORTED_KEYS = {"name", "description"}


class FrontmatterMetadata(TypedDict, total=False):
    name: str
    description: str


def read_markdown_text(doc_path: Path) -> str:
    if not doc_path.is_file():
        return ""
    try:
        text = doc_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    return text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")


def split_frontmatter(text: str) -> tuple[FrontmatterMetadata, str]:
    normalized = str(text or "")
    if not normalized.startswith(f"{_FRONTMATTER_DELIMITER}\n"):
        return {}, normalized

    lines = normalized.split("\n")
    if not lines or lines[0] != _FRONTMATTER_DELIMITER:
        return {}, normalized

    end_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == _FRONTMATTER_DELIMITER:
            end_index = index
            break
    if end_index is None:
        return {}, normalized

    raw_block = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :])
    return parse_frontmatter_block(raw_block), body


def parse_frontmatter_block(raw: str) -> FrontmatterMetadata:
    lines = str(raw or "").split("\n")
    metadata: FrontmatterMetadata = {}
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            index += 1
            continue
        if line[:1].isspace():
            index += 1
            continue
        if ":" not in line:
            index += 1
            continue

        key, _, remainder = line.partition(":")
        normalized_key = key.strip()
        if normalized_key not in _SUPPORTED_KEYS:
            index += 1
            continue

        value = remainder.strip()
        if value in {">", "|"}:
            block_lines: list[str] = []
            folded = value == ">"
            index += 1

            while index < len(lines):
                candidate = lines[index]
                if not candidate.strip():
                    block_lines.append("")
                    index += 1
                    continue
                if candidate.startswith(" ") or candidate.startswith("\t"):
                    block_lines.append(candidate.lstrip(" \t"))
                    index += 1
                    continue
                break
            normalized_value = _normalize_block_scalar(block_lines, folded=folded)
        else:
            normalized_value = strip_inline_comment(strip_wrapping_quotes(value))
            index += 1

        if normalized_value:
            metadata[normalized_key] = normalized_value

    return metadata


def strip_frontmatter(text: str) -> str:
    _, body = split_frontmatter(text)
    return body


def build_body_synopsis(
    text: str,
    *,
    max_lines: int = 6,
    max_chars: int = 400,
) -> str:
    body = strip_frontmatter(text)
    lines: list[str] = []
    current_chars = 0
    for raw_line in body.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        lines.append(line)
        current_chars += len(line)
        if len(lines) >= max_lines or current_chars >= max_chars:
            break
    synopsis = "\n".join(lines)
    if len(synopsis) > max_chars:
        return synopsis[: max_chars - 1] + "\u2026"
    return synopsis


def parse_markdown_metadata(doc_path: Path) -> FrontmatterMetadata:
    text = read_markdown_text(doc_path)
    if not text:
        return {}
    metadata, _ = split_frontmatter(text)
    return metadata


def parse_markdown_description(doc_path: Path) -> str:
    metadata = parse_markdown_metadata(doc_path)
    return str(metadata.get("description", "")).strip()


def parse_markdown_name(doc_path: Path) -> str:
    metadata = parse_markdown_metadata(doc_path)
    return str(metadata.get("name", "")).strip()


def parse_markdown_synopsis(
    doc_path: Path,
    *,
    max_lines: int = 6,
    max_chars: int = 400,
) -> str:
    text = read_markdown_text(doc_path)
    if not text:
        return ""
    return build_body_synopsis(text, max_lines=max_lines, max_chars=max_chars)


def _normalize_block_scalar(lines: list[str], *, folded: bool) -> str:
    if not lines:
        return ""
    trimmed = _trim_blank_edges(lines)
    if not trimmed:
        return ""

    if folded:
        parts: list[str] = []
        for line in trimmed:
            if not line:
                parts.append("\n")
                continue
            if parts and parts[-1] != "\n":
                parts.append(" ")
            parts.append(line.strip())
        return "".join(parts).replace("\n ", "\n").strip()

    return "\n".join(line.rstrip() for line in trimmed).strip()


def _trim_blank_edges(lines: list[str]) -> list[str]:
    start = 0
    end = len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]


__all__ = [
    "FrontmatterMetadata",
    "build_body_synopsis",
    "parse_frontmatter_block",
    "parse_markdown_description",
    "parse_markdown_metadata",
    "parse_markdown_name",
    "parse_markdown_synopsis",
    "read_markdown_text",
    "split_frontmatter",
    "strip_frontmatter",
]
