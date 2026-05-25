from __future__ import annotations
from typing import Optional

import re
from pathlib import Path

from packaging._shared.common.local_path_detection import redact_local_traces_in_text
from packaging._shared.common.constants import PII_PATTERNS
from packaging._shared.common.fs import (
    is_within,
    iter_workspace_files,
    read_text,
    relpath,
)
from packaging.configure.sensitive.text_redact_rules import (
    CLEAN_COLLAPSE_BLANKS,
    CLEAN_INLINE_PII,
    CLEAN_MEMORY_PII_LINES,
    CLEAN_STOP_IF_BLANK_USER_TEMPLATE,
    CLEAN_TOOLS_FIELDS,
    CLEAN_TOOLS_PATTERNS,
    CLEAN_USER_FIELDS_REDACTED,
    CLEAN_USER_FIELDS_TO_FILL,
    MEMORY_PII_LINE_PATTERNS,
    MODE_CLEAN_STEPS,
    SPECIAL_CLEAN_FILENAMES,
    SPECIAL_CLEAN_RELATIVE_FILES,
    TOOLS_FIELD_PATTERN,
    TOOLS_PATTERNS,
    USER_EMPTY_PLACEHOLDER_PATTERN,
    USER_FIELD_PATTERN,
    USER_MARKDOWN_FIELD_PATTERN,
    USER_TABLE_PATTERN,
)


def _replace_patterns(text: str, patterns: list[re.Pattern[str]], replacement: str) -> tuple[str, int]:
    updated = text
    replacements = 0
    for pattern in patterns:
        updated, count = pattern.subn(replacement, updated)
        replacements += count
    return updated, replacements


def _replace_line_values(
    text: str,
    pattern: re.Pattern[str],
    replacement: str,
    *,
    suffix_group: Optional[int] = None,
) -> tuple[str, int]:
    def replace_match(match: re.Match[str]) -> str:
        suffix = ""
        if suffix_group is not None:
            suffix = match.group(suffix_group) or ""
        return f"{match.group(1)}{replacement}{suffix}"

    return pattern.subn(replace_match, text)


def _detect_clean_mode(relative_file: str) -> str:
    normalized_relative = Path(relative_file).as_posix()
    if normalized_relative == ".openclaw/workspace/AGENTS.md":
        return "workspace_agents"
    if normalized_relative == ".openclaw/workspace/SOUL.md":
        return "workspace_soul"

    filename = Path(relative_file).name
    if filename == "MEMORY.md":
        return "memory"
    if filename == "TOOLS.md":
        return "tools"
    if filename == "USER.md":
        return "user_template"
    if filename == "HEARTBEAT.md":
        return "heartbeat"
    return "generic"


def _is_user_template_blank(text: str) -> bool:
    field_lines = USER_FIELD_PATTERN.findall(text) + USER_MARKDOWN_FIELD_PATTERN.findall(text)
    if not field_lines:
        return False
    placeholder_hits = len(USER_EMPTY_PLACEHOLDER_PATTERN.findall(text))
    return placeholder_hits >= len(field_lines) * 0.6


def _replace_memory_pii_lines(text: str) -> tuple[str, int]:
    cleaned = text
    replacements = 0
    for pattern in MEMORY_PII_LINE_PATTERNS:
        cleaned, count = pattern.subn("", cleaned)
        replacements += count
    return cleaned, replacements


def _replace_user_field_values(text: str, replacement: str) -> tuple[str, int]:
    cleaned, markdown_count = _replace_line_values(text, USER_MARKDOWN_FIELD_PATTERN, replacement)
    cleaned, field_count = _replace_line_values(cleaned, USER_FIELD_PATTERN, replacement)
    cleaned, table_count = _replace_line_values(cleaned, USER_TABLE_PATTERN, replacement, suffix_group=3)
    return cleaned, markdown_count + field_count + table_count


def _apply_clean_step(text: str, step: str) -> tuple[str, int, bool]:
    if step == CLEAN_STOP_IF_BLANK_USER_TEMPLATE:
        return text, 0, _is_user_template_blank(text)
    if step == CLEAN_MEMORY_PII_LINES:
        cleaned, count = _replace_memory_pii_lines(text)
        return cleaned, count, False
    if step == CLEAN_INLINE_PII:
        cleaned, count = _replace_patterns(text, list(PII_PATTERNS), "[redacted]")
        return cleaned, count, False
    if step == CLEAN_TOOLS_PATTERNS:
        cleaned, count = _replace_patterns(text, TOOLS_PATTERNS, "[redacted]")
        return cleaned, count, False
    if step == CLEAN_TOOLS_FIELDS:
        cleaned, count = _replace_line_values(text, TOOLS_FIELD_PATTERN, "[redacted]")
        return cleaned, count, False
    if step == CLEAN_USER_FIELDS_TO_FILL:
        cleaned, count = _replace_user_field_values(text, "[to_fill]")
        return cleaned, count, False
    if step == CLEAN_USER_FIELDS_REDACTED:
        cleaned, count = _replace_user_field_values(text, "[redacted]")
        return cleaned, count, False
    if step == CLEAN_COLLAPSE_BLANKS:
        return re.sub(r"\n{3,}", "\n\n", text), 0, False
    raise ValueError(f"unknown clean step: {step}")


def _clean_text_for_mode(text: str, mode: str) -> tuple[str, int]:
    cleaned = text
    replacements = 0
    for step in MODE_CLEAN_STEPS.get(mode, MODE_CLEAN_STEPS["generic"]):
        cleaned, count, should_stop = _apply_clean_step(cleaned, step)
        replacements += count
        if should_stop:
            return cleaned, replacements
    return cleaned, replacements


def _collect_examples(original: str, cleaned: str, *, max_examples: int = 3) -> dict:
    orig_lines = [line.strip() for line in original.splitlines() if line.strip()]
    clean_lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    clean_set = set(clean_lines)

    removed: list[str] = []
    kept: list[str] = []
    for line in orig_lines:
        if line not in clean_set and len(removed) < max_examples:

            removed.append(line[:120] + ("…" if len(line) > 120 else ""))
        elif line in clean_set and "[redacted]" not in line and "[to_fill]" not in line and len(kept) < max_examples:
            kept.append(line[:120] + ("…" if len(line) > 120 else ""))


    for line in clean_lines:
        if ("[redacted]" in line or "[to_fill]" in line) and len(removed) < max_examples:
            for orig_line in orig_lines:
                if orig_line not in clean_set and orig_line not in removed:
                    removed.append(orig_line[:120] + ("…" if len(orig_line) > 120 else ""))
                    break

    return {"removed_examples": removed, "kept_examples": kept}


def clean_text_content(relative_file: str, text: str) -> tuple[str, dict]:
    mode = _detect_clean_mode(relative_file)
    cleaned, replacements = _clean_text_for_mode(text, mode)
    examples = _collect_examples(text, cleaned) if replacements > 0 else {"removed_examples": [], "kept_examples": []}
    return cleaned, {
        "file": relative_file,
        "mode": mode,
        "replacements": replacements,
        "removed_examples": examples["removed_examples"],
        "kept_examples": examples["kept_examples"],
        "preview": cleaned[:200],
    }


def _safe_relative_file(staging_root: Path, relative_file: str) -> Path:
    candidate = (staging_root / relative_file).resolve()

    if not is_within(candidate, staging_root):
        raise ValueError("file path escapes the staging directory")
    return candidate


def clean_staging_file(staging_root: Path, relative_file: str) -> dict:
    target = _safe_relative_file(staging_root, relative_file)
    if not target.is_file():
        raise ValueError(f"file does not exist: {target}")

    text, encoding = read_text(target)
    if text is None or encoding is None:
        raise ValueError(f"file is not a supported text file: {target}")

    cleaned, summary = clean_text_content(relative_file, text)
    target.write_text(cleaned, encoding=encoding)
    return summary


def clean_special_files_in_staging(staging_root: Path) -> dict:
    items: list[dict] = []
    total_replacements = 0
    for path in sorted(iter_workspace_files(staging_root, skip_system=False)):
        relative_file = relpath(path, staging_root)
        if (
            path.name not in SPECIAL_CLEAN_FILENAMES
            and relative_file not in SPECIAL_CLEAN_RELATIVE_FILES
        ) or not path.is_file():
            continue
        summary = clean_staging_file(staging_root, relative_file)
        items.append(
            {
                "file": summary["file"],
                "mode": summary["mode"],
                "replacements": summary["replacements"],
                "removed_examples": summary.get("removed_examples", []),
                "kept_examples": summary.get("kept_examples", []),
            }
        )
        total_replacements += int(summary["replacements"])
    return {
        "processed_file_count": len(items),
        "total_replacements": total_replacements,
        "items": items,
    }


def replace_local_patterns(text: str, *, source_path: Optional[Path] = None) -> tuple[str, int]:
    updated, replacements = redact_local_traces_in_text(
        text,
        replacement="[removed]",
        source_path=source_path,
    )
    for pattern in TOOLS_PATTERNS:
        updated, count = pattern.subn("[removed]", updated)
        replacements += count
    return updated, replacements


def redact_markdown_instruction(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    cleaned, summary = clean_text_content(path.name, text)
    cleaned, local_count = replace_local_patterns(cleaned, source_path=path)
    replacements = int(summary["replacements"]) + local_count
    if replacements:
        path.write_text(cleaned, encoding="utf-8")
    return replacements


__all__ = [
    "TOOLS_PATTERNS",
    "clean_special_files_in_staging",
    "clean_staging_file",
    "clean_text_content",
    "redact_markdown_instruction",
    "replace_local_patterns",
]
