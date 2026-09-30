from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
from typing import Iterable, Optional

from .constants import (
    DEVELOPER_FALLBACK_DIR_PATH,
    DEVELOPER_WORK_DIR_PATH,
    SKILL_CONFIG_PATH,
    PUBLISHER_ROOT_PATH,
)
from .exclusion_rules import (
    HIGH_RISK_FILE_BASENAMES,
    STAGE_EXCLUDED_DIRS,
    STAGE_EXCLUDED_SUFFIXES,
)
from .fs import display_stage_path, is_within, looks_like_absolute_symlink, looks_like_virtualenv_dir, relpath as fs_relpath



_LOCAL_HOST_STATE_ROOTS = tuple(
    path.resolve() for path in (DEVELOPER_WORK_DIR_PATH, DEVELOPER_FALLBACK_DIR_PATH)
)
_LOCAL_HOST_STATE_FILES = (SKILL_CONFIG_PATH.resolve(),)
_LOCAL_HOST_STATE_STAGING_ROOTS = tuple(
    (root / "staging").resolve() for root in (DEVELOPER_WORK_DIR_PATH, DEVELOPER_FALLBACK_DIR_PATH)
)


def should_skip_packaged_relpath(
    relpath: str,
    *,
    is_dir: bool,
    excluded_relpath_prefixes: tuple[str, ...] = (),
) -> bool:
    pure = PurePosixPath(relpath.rstrip("/"))
    name = pure.name
    if not name:
        return False
    parts = tuple(part for part in pure.parts if part and part != ".")
    for prefix in excluded_relpath_prefixes:
        prefix_parts = tuple(part for part in PurePosixPath(prefix.rstrip("/")).parts if part and part != ".")
        if prefix_parts and parts[: len(prefix_parts)] == prefix_parts:
            return True
    if any(part in STAGE_EXCLUDED_DIRS for part in parts):
        return True
    if not is_dir:
        if name.lower() in HIGH_RISK_FILE_BASENAMES:
            return True
        if any(name.endswith(suffix) for suffix in STAGE_EXCLUDED_SUFFIXES):
            return True
    return False


def is_publisher_source_path(source_path: Path) -> bool:
    """Return True for capafy-publisher source and all descendants.

    The Publisher may live inside a runtime workspace so it can publish sibling
    skills, but its own source is an internal implementation detail and must
    never cross the staging/package boundary.
    """
    try:
        resolved = source_path.expanduser().resolve(strict=False)
        return resolved == PUBLISHER_ROOT_PATH or PUBLISHER_ROOT_PATH in resolved.parents
    except OSError:
        return False


def _is_local_host_state_path(source_path: Path) -> bool:
    resolved_source = source_path.resolve()
    if any(resolved_source == local_file for local_file in _LOCAL_HOST_STATE_FILES):
        return True
    if any(is_within(resolved_source, staging_root) for staging_root in _LOCAL_HOST_STATE_STAGING_ROOTS):

        return False
    return any(is_within(resolved_source, root) for root in _LOCAL_HOST_STATE_ROOTS)


def should_skip_packaged_path(
    source_path: Path,
    relpath: str,
    *,
    is_dir: bool,
    excluded_relpath_prefixes: tuple[str, ...] = (),
) -> bool:
    if is_publisher_source_path(source_path):
        return True
    if _is_local_host_state_path(source_path):
        return True
    return should_skip_packaged_relpath(
        relpath,
        is_dir=is_dir,
        excluded_relpath_prefixes=excluded_relpath_prefixes,
    )


def iter_packaged_files(
    root: Path,
) -> Iterable[Path]:
    for current, dirnames, filenames in os.walk(root, topdown=True):
        current_path = Path(current)
        current_relpath = fs_relpath(current_path, root)
        kept_dirs: list[str] = []
        for dirname in sorted(dirnames):
            relpath = display_stage_path(current_relpath, dirname)
            if looks_like_virtualenv_dir(current_path / dirname):
                continue
            if looks_like_absolute_symlink(current_path / dirname):
                continue
            if should_skip_packaged_path(
                current_path / dirname,
                relpath,
                is_dir=True,
            ):
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in sorted(filenames):
            relpath = display_stage_path(current_relpath, filename)
            if looks_like_absolute_symlink(current_path / filename):
                continue
            if should_skip_packaged_path(
                current_path / filename,
                relpath,
                is_dir=False,
            ):
                continue
            yield current_path / filename


def matches_workspace_allowlist(
    display_path: str,
    workspace_allowlist: Optional[set[str]],
    *,
    is_dir: bool,
) -> bool:
    if workspace_allowlist is None:
        return True

    normalized = PurePosixPath(display_path.rstrip("/")).as_posix()
    if not normalized or normalized == ".":
        return True


    if normalized in workspace_allowlist:
        return True


    if any(normalized.startswith(f"{prefix}/") for prefix in workspace_allowlist):
        return True


    if is_dir:
        if any(entry.startswith(f"{normalized}/") for entry in workspace_allowlist):
            return True

    return False

__all__ = [
    "is_publisher_source_path",
    "iter_packaged_files",
    "matches_workspace_allowlist",
    "should_skip_packaged_path",
    "should_skip_packaged_relpath",
]
