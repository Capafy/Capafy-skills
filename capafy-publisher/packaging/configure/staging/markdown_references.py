from __future__ import annotations
from typing import Optional

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from packaging._shared.common.fs import (
    windows_drive_mount_candidates as _windows_drive_mount_candidates,
    windows_path_parts as _windows_path_parts,
)
from packaging.configure.selection.local_ref_confirmation import local_reference_should_be_staged
from packaging.configure.staging.markdown_reference_paths import (
    looks_like_local_destination,
    resolve_reference,
    unwrap_destination,
)
from packaging.configure.staging.tree_copy import copy_tree_file
from packaging._shared.contracts.selectable import is_instruction_doc
from packaging._shared.contracts.stage_plan import StagePlan


_MARKDOWN_LINK_PATTERN = re.compile(
    r"(?P<prefix>!?\[[^\]]*\]\()(?P<dest><[^>\r\n]+>|[^\s)\r\n]+)(?P<suffix>(?:\s+['\"][^)\r\n]*['\"])?\))"
)
_REFERENCE_LINK_PATTERN = re.compile(
    r"(?m)^(?P<prefix>\s*\[[^\]]+\]:\s*)(?P<dest><[^>\r\n]+>|[^\s\r\n]+)(?P<suffix>.*)$"
)
_INLINE_CODE_PATTERN = re.compile(r"`(?P<dest>[^`\r\n]+)`")
_PLAIN_PATH_PATTERN = re.compile(
    r"(?<![\w@])(?P<dest>(?:~|\.{1,2}|/|[A-Za-z]:[\\/])?[^\s`\"'<>()[\]]+\.[A-Za-z0-9]{1,12})(?![\w])"
)

@dataclass(frozen=True)
class _Reference:
    start: int
    end: int
    value: str


def _is_markdown_reference_entry(path: Path) -> bool:
    return path.is_file() and is_instruction_doc(path.name)


def _iter_reference_candidates(text: str) -> list[_Reference]:
    candidates: list[_Reference] = []

    for pattern in (_MARKDOWN_LINK_PATTERN, _REFERENCE_LINK_PATTERN, _INLINE_CODE_PATTERN):
        for match in pattern.finditer(text):
            candidates.append(_Reference(match.start("dest"), match.end("dest"), match.group("dest")))

    for match in _PLAIN_PATH_PATTERN.finditer(text):
        value = match.group("dest")
        if not looks_like_local_destination(value):
            continue
        candidates.append(_Reference(match.start("dest"), match.end("dest"), value))

    candidates.sort(key=lambda item: (item.start, item.end))
    deduped: list[_Reference] = []
    occupied: list[tuple[int, int]] = []
    for item in candidates:
        if any(not (item.end <= start or item.start >= end) for start, end in occupied):
            continue
        deduped.append(item)
        occupied.append((item.start, item.end))
    return deduped


def _relative_reference(from_doc: Path, target_file: Path) -> str:
    try:
        rel = target_file.relative_to(from_doc.parent)
        return PurePosixPath(rel.as_posix()).as_posix()
    except ValueError:

        import os

        return PurePosixPath(os.path.relpath(target_file, from_doc.parent)).as_posix()


def stage_direct_markdown_file_references(
    source_doc: Path,
    target_doc: Path,
    *,
    stage_plan: Optional[StagePlan] = None,
) -> int:
    if not _is_markdown_reference_entry(source_doc) or not target_doc.is_file():
        return 0
    try:
        text = source_doc.read_text(encoding="utf-8")
    except OSError:
        return 0

    replacements: list[tuple[int, int, str]] = []
    copied_targets: set[str] = set()
    copied_count = 0
    for reference in _iter_reference_candidates(text):
        resolved = resolve_reference(
            source_doc,
            reference.value,
            windows_drive_mount_candidates=_windows_drive_mount_candidates,
            windows_path_parts=_windows_path_parts,
        )
        if resolved is None:
            continue
        source_file, relative_source, suffix = resolved
        if is_instruction_doc(source_file.name) and not local_reference_should_be_staged(source_file, stage_plan):
            continue
        target_file = target_doc.parent / relative_source
        if target_file.resolve(strict=False) == target_doc.resolve(strict=False):
            continue
        target_key = target_file.as_posix()
        if target_key not in copied_targets:
            copy_tree_file(source_file, target_file)
            copied_targets.add(target_key)
            copied_count += 1
        relative_target = _relative_reference(target_doc, target_file)
        leading, _value, trailing = unwrap_destination(reference.value)
        replacement = f"{leading}{relative_target}{suffix}{trailing}"
        replacements.append((reference.start, reference.end, replacement))

    if replacements:
        updated = text
        for start, end, replacement in reversed(replacements):
            updated = f"{updated[:start]}{replacement}{updated[end:]}"
        target_doc.write_text(updated, encoding="utf-8")
    return copied_count


__all__ = ["stage_direct_markdown_file_references"]
