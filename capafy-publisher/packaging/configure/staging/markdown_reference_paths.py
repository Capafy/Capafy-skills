from __future__ import annotations
from typing import Optional

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

from packaging._shared.common.home import home_roots_from_env, safe_expanduser_path
from packaging._shared.common.fs import (
    is_within,
    looks_like_absolute_symlink,
    windows_drive_mount_candidates as _default_windows_drive_mount_candidates,
    windows_path_parts as _default_windows_path_parts,
)
from packaging.configure.exclusion import looks_like_high_risk_file


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
        aliases.extend([
            f"/mnt/{drive}/{rest}",
            f"/{drive}/{rest}",
        ])

    wsl_match = _WSL_MOUNT_PATH_PATTERN.match(normalized)
    if wsl_match:
        drive = wsl_match.group("drive")
        rest = wsl_match.group("rest").strip("/")
        aliases.extend([
            f"{drive.upper()}:/{rest}",
            f"/{drive.lower()}/{rest}",
        ])

    short_drive_match = _WSL_SHORT_DRIVE_PATH_PATTERN.match(normalized)
    if short_drive_match:
        drive = short_drive_match.group("drive")
        rest = short_drive_match.group("rest").strip("/")
        aliases.extend([
            f"{drive.upper()}:/{rest}",
            f"/mnt/{drive.lower()}/{rest}",
        ])

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
    *,
    home_aliases: Callable[[], list[tuple[str, Path]]] = current_home_aliases,
) -> list[Path]:
    normalized_path = normalize_path_text(path_part)
    normalized_path_key = normalized_path.casefold()
    candidates: list[Path] = []
    for alias, home_root in home_aliases():
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
    *,
    home_aliases: Callable[[], list[tuple[str, Path]]] = current_home_aliases,
    windows_drive_mount_candidates: Callable[[str], list[Path]] = _default_windows_drive_mount_candidates,
    windows_path_parts: Callable[[str], list[str]] = _default_windows_path_parts,
) -> list[Path]:
    windows_match = _WINDOWS_DRIVE_PATH_PATTERN.match(path_part)
    if windows_match:
        rest_parts = windows_path_parts(windows_match.group("rest"))
        return dedupe_path_candidates([
            safe_expanduser_path(path_part),
            *(
                root.joinpath(*rest_parts)
                for root in windows_drive_mount_candidates(windows_match.group("drive"))
            ),
            *current_home_alias_candidates(path_part, home_aliases=home_aliases),
        ])

    candidate = safe_expanduser_path(path_part)
    if not candidate.is_absolute():
        candidate = source_doc.parent / candidate
    return dedupe_path_candidates([
        candidate,
        *current_home_alias_candidates(path_part, home_aliases=home_aliases),
    ])


def resolve_reference(
    source_doc: Path,
    raw_value: str,
    *,
    home_aliases: Callable[[], list[tuple[str, Path]]] = current_home_aliases,
    windows_drive_mount_candidates: Callable[[str], list[Path]] = _default_windows_drive_mount_candidates,
    windows_path_parts: Callable[[str], list[str]] = _default_windows_path_parts,
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
        home_aliases=home_aliases,
        windows_drive_mount_candidates=windows_drive_mount_candidates,
        windows_path_parts=windows_path_parts,
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


__all__ = [
    "current_home_aliases",
    "current_home_alias_candidates",
    "dedupe_path_candidates",
    "home_alias_texts",
    "looks_like_local_destination",
    "normalize_path_text",
    "path_candidates",
    "resolve_reference",
    "strip_fragment_and_query",
    "unwrap_destination",
]
