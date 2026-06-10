from __future__ import annotations
from typing import Optional

from contextlib import suppress
import os
import re
from pathlib import Path

from packaging._shared.common.fs import (
    is_within,
    windows_drive_mount_candidates as _windows_drive_mount_candidates,
    windows_path_parts as _windows_path_parts,
)
from packaging._shared.config_files.toml_loader import safe_toml_loads, tomllib


WINDOWS_DRIVE_PATH_PATTERN = re.compile(r"^(?P<drive>[A-Za-z]):[\\/](?P<rest>.*)$")
_LOCAL_PATH_PLACEHOLDER = "LOCAL_PATH_REDACTED"


def path_candidates(raw_value: str) -> list[Path]:
    candidates = [Path(raw_value).expanduser()]
    match = WINDOWS_DRIVE_PATH_PATTERN.match(raw_value.strip())
    if not match:
        return candidates

    parts = _windows_path_parts(match.group("rest"))
    for root in _windows_drive_mount_candidates(match.group("drive")):
        candidates.append(root.joinpath(*parts))
    return candidates


def windows_user_home_candidates(raw_value: str) -> list[Path]:
    match = WINDOWS_DRIVE_PATH_PATTERN.match(raw_value.strip())
    if not match:
        return []
    parts = _windows_path_parts(match.group("rest"))
    if len(parts) < 2:
        return []
    if parts[0].lower() not in {"users", "documents and settings"}:
        return []
    home_value = f"{match.group('drive')}:{os.sep}{parts[0]}{os.sep}{parts[1]}"
    return path_candidates(home_value)


def allowed_roots(raw_value: str) -> list[Path]:
    roots = [Path.home()]
    with suppress(OSError):
        roots.append(Path.home().expanduser().resolve())
    userprofile = os.environ.get("USERPROFILE", "").strip()
    if userprofile:
        roots.extend(path_candidates(userprofile))
    homedrive = os.environ.get("HOMEDRIVE", "").strip()
    homepath = os.environ.get("HOMEPATH", "").strip()
    if homedrive and homepath:
        roots.extend(path_candidates(f"{homedrive}{homepath}"))
    roots.extend(windows_user_home_candidates(raw_value))
    return roots


def looks_like_platform_managed_placeholder(raw_value: str) -> bool:
    value = raw_value.strip().lower()
    return (
        value == _LOCAL_PATH_PLACEHOLDER.lower()
        or value == "platform_managed_key"
        or value.startswith("platform_managed_value_")
    )


def looks_like_local_path(raw_value: str) -> bool:
    value = raw_value.strip()
    if not value:
        return False
    return (
        value.startswith(("~", "/", "./", "../", "\\\\"))
        or WINDOWS_DRIVE_PATH_PATTERN.match(value) is not None
    )


def is_allowed_source_path(path: Path, raw_value: str) -> bool:
    resolved = path.resolve()
    for root in allowed_roots(raw_value):
        try:
            resolved_root = root.expanduser().resolve()
        except OSError:
            continue
        if is_within(resolved, resolved_root):
            return True
    return False


def parse_toml_local_file_value(line: str, field_name: str, fallback_value: str) -> str:
    try:
        payload = safe_toml_loads(line)
    except tomllib.TOMLDecodeError:
        return fallback_value
    value = payload.get(field_name)
    if isinstance(value, str):
        return value
    return fallback_value


def resolve_codex_local_config_file_source(raw_value: str) -> Optional[Path]:
    for candidate in path_candidates(raw_value):
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        if is_allowed_source_path(resolved, raw_value):
            return resolved
    return None


def resolve_codex_local_config_file_source_with_roots(
    raw_value: str,
    roots: list[Path],
) -> Optional[Path]:
    for candidate in path_candidates(raw_value):
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        for root in roots:
            try:
                resolved_root = root.expanduser().resolve()
            except OSError:
                continue
            if is_within(resolved, resolved_root):
                return resolved
    return None


__all__ = [
    "WINDOWS_DRIVE_PATH_PATTERN",
    "allowed_roots",
    "is_allowed_source_path",
    "looks_like_local_path",
    "looks_like_platform_managed_placeholder",
    "parse_toml_local_file_value",
    "path_candidates",
    "resolve_codex_local_config_file_source",
    "resolve_codex_local_config_file_source_with_roots",
    "windows_user_home_candidates",
]
