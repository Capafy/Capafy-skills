from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Optional
from urllib.parse import unquote

from packaging.common.exclusion_rules import looks_like_high_risk_file
from packaging.common.fs import (
    is_within,
    looks_like_absolute_symlink,
    windows_drive_mount_candidates as _windows_drive_mount_candidates,
    windows_path_parts as _windows_path_parts,
)
from packaging.common.home import home_roots_from_env, safe_expanduser_path
from packaging.common.instruction_docs import is_instruction_doc
from packaging.common.packaged_files import should_skip_packaged_path
from packaging.runtime.stage_plan import StagePlan
from packaging.publish.selection.local_ref_confirmation import local_reference_should_be_staged
from packaging.publish.staging.exclusions import should_skip_high_risk_stage_file
from packaging.publish.staging.tree_copy import copy_tree_file


_URI_SCHEME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_WINDOWS_DRIVE_PATTERN = re.compile(r"^[A-Za-z]:[\\/]")
_WINDOWS_DRIVE_PATH_PATTERN = re.compile(r"^(?P<drive>[A-Za-z]):[\\/](?P<rest>.*)$")
_LOCAL_PATH_HINT_PATTERN = re.compile(r"^(?:~|\.{1,2}/|/|[A-Za-z]:[\\/])|/")
_WSL_MOUNT_PATH_PATTERN = re.compile(r"^/mnt/(?P<drive>[A-Za-z])/(?P<rest>.+)$")
_WSL_SHORT_DRIVE_PATH_PATTERN = re.compile(r"^/(?P<drive>[A-Za-z])/(?P<rest>.+)$")


def unwrap_destination(raw_value: str) -> tuple[str, str, str]:
    leading = ""
    trailing = ""
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == "<" and value[-1] == ">":
        leading = "<"
        trailing = ">"
        value = value[1:-1].strip()
    return leading, value, trailing


def strip_fragment_and_query(value: str) -> tuple[str, str]:
    split_at = len(value)
    for marker in ("#", "?"):
        index = value.find(marker)
        if index >= 0:
            split_at = min(split_at, index)
    return value[:split_at], value[split_at:]


def looks_like_local_destination(value: str) -> bool:
    if not value or value.startswith("#"):
        return False
    if _URI_SCHEME_PATTERN.match(value) and not _WINDOWS_DRIVE_PATTERN.match(value):
        return False
    if _LOCAL_PATH_HINT_PATTERN.search(value):
        return True
    name = PurePosixPath(value).name
    if name == ".env" or name.startswith(".env."):
        return True
    return bool(PurePosixPath(value).suffix)


def normalize_path_text(value: str) -> str:
    normalized = str(value or "").replace("\\", "/").strip()
    normalized = re.sub(r"/+", "/", normalized)
    if normalized.startswith("/") and not normalized.startswith("//"):
        return normalized.rstrip("/") or "/"
    return normalized.rstrip("/")


def home_alias_texts(home_root: Path) -> list[str]:
    normalized = normalize_path_text(str(home_root))
    aliases = [normalized]

    windows_match = _WINDOWS_DRIVE_PATH_PATTERN.match(normalized)
    if windows_match:
        drive = windows_match.group("drive").lower()
        rest = windows_match.group("rest").strip("/")
        aliases.extend(
            [
                f"/mnt/{drive}/{rest}",
                f"/{drive}/{rest}",
            ]
        )

    wsl_match = _WSL_MOUNT_PATH_PATTERN.match(normalized)
    if wsl_match:
        drive = wsl_match.group("drive")
        rest = wsl_match.group("rest").strip("/")
        aliases.extend(
            [
                f"{drive.upper()}:/{rest}",
                f"/{drive.lower()}/{rest}",
            ]
        )

    short_drive_match = _WSL_SHORT_DRIVE_PATH_PATTERN.match(normalized)
    if short_drive_match:
        drive = short_drive_match.group("drive")
        rest = short_drive_match.group("rest").strip("/")
        aliases.extend(
            [
                f"{drive.upper()}:/{rest}",
                f"/mnt/{drive.lower()}/{rest}",
            ]
        )

    deduped: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        key = normalize_path_text(alias).casefold()
        if key and key not in seen:
            deduped.append(alias)
            seen.add(key)
    return deduped


def current_home_aliases() -> list[tuple[str, Path]]:
    aliases: list[tuple[str, Path]] = []
    seen: set[tuple[str, str]] = set()
    for home_root in home_roots_from_env():
        for alias in home_alias_texts(home_root):
            key = (
                normalize_path_text(alias).casefold(),
                normalize_path_text(str(home_root)).casefold(),
            )
            if key in seen:
                continue
            aliases.append((alias, home_root))
            seen.add(key)
    return aliases


def current_home_alias_candidates(
    path_part: str,
) -> list[Path]:
    normalized_path = normalize_path_text(path_part)
    normalized_path_key = normalized_path.casefold()
    candidates: list[Path] = []
    for alias, home_root in current_home_aliases():
        normalized_alias = normalize_path_text(alias)
        normalized_alias_key = normalized_alias.casefold()
        if normalized_path_key == normalized_alias_key:
            candidates.append(home_root)
            continue
        if not normalized_path_key.startswith(f"{normalized_alias_key}/"):
            continue
        relative = normalized_path[len(normalized_alias) + 1 :]
        relative_parts = [part for part in relative.strip("/").split("/") if part]
        candidates.append(home_root.joinpath(*relative_parts))
    return candidates


def dedupe_path_candidates(candidates: list[Path]) -> list[Path]:
    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.as_posix()
        if key in seen:
            continue
        deduped.append(candidate)
        seen.add(key)
    return deduped


def path_candidates(
    source_doc: Path,
    path_part: str,
) -> list[Path]:
    windows_match = _WINDOWS_DRIVE_PATH_PATTERN.match(path_part)
    if windows_match:
        rest_parts = _windows_path_parts(windows_match.group("rest"))
        return dedupe_path_candidates(
            [
                safe_expanduser_path(path_part),
                *(
                    root.joinpath(*rest_parts)
                    for root in _windows_drive_mount_candidates(windows_match.group("drive"))
                ),
                *current_home_alias_candidates(path_part),
            ]
        )

    candidate = safe_expanduser_path(path_part)
    if not candidate.is_absolute():
        candidate = source_doc.parent / candidate
    return dedupe_path_candidates(
        [
            candidate,
            *current_home_alias_candidates(path_part),
        ]
    )


def resolve_reference(
    source_doc: Path,
    raw_value: str,
) -> Optional[tuple[Path, str, str]]:
    _leading, value, _trailing = unwrap_destination(raw_value)
    path_part, suffix = strip_fragment_and_query(value)
    path_part = unquote(path_part.strip())
    if not looks_like_local_destination(path_part):
        return None

    source_root = source_doc.parent.resolve(strict=True)
    for candidate in path_candidates(
        source_doc,
        path_part,
    ):
        if candidate.is_symlink() or looks_like_absolute_symlink(candidate):
            continue
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            continue
        if not resolved.is_file():
            continue
        if not is_within(resolved, source_root):
            continue
        relative_path = resolved.relative_to(source_root).as_posix()
        if looks_like_high_risk_file(relative_path):
            continue
        return resolved, relative_path, suffix
    return None


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
    staging_root: Path,
    target: object,
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
        )
        if resolved is None:
            continue
        source_file, relative_source, suffix = resolved
        if is_instruction_doc(source_file.name) and not local_reference_should_be_staged(source_file, stage_plan):
            continue
        target_file = target_doc.parent / relative_source
        target_relpath = target_file.relative_to(staging_root).as_posix()
        if should_skip_packaged_path(source_file, target_relpath, is_dir=False):
            continue
        if should_skip_high_risk_stage_file(target, target_relpath):
            continue
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


__all__ = [
    "current_home_alias_candidates",
    "current_home_aliases",
    "dedupe_path_candidates",
    "home_alias_texts",
    "looks_like_local_destination",
    "normalize_path_text",
    "path_candidates",
    "resolve_reference",
    "stage_direct_markdown_file_references",
    "strip_fragment_and_query",
    "unwrap_destination",
]
