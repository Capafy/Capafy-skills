from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
from typing import Iterable

from .constants import (
    DEVELOPER_FALLBACK_DIR_PATH,
    DEVELOPER_WORK_DIR_PATH,
    SKILL_CONFIG_PATH,
)
from .exclusion_rules import (
    CREDENTIAL_EXCLUDED_DIRS,
    PRIVATE_KEY_FILE_BASENAMES,
    STAGE_EXCLUDED_DIRS,
    STAGE_EXCLUDED_FILES,
    STAGE_EXCLUDED_NAME_PATTERNS,
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


def _matches_skill_runtime_output_parts(
    parts: list[str],
    *,
    allow_any_second_part_run: bool,
) -> bool:
    if not parts:
        return False
    if parts[0] == "run":
        return True
    if allow_any_second_part_run and len(parts) >= 2 and parts[1] == "run":
        return True
    for index in range(len(parts) - 2):
        if parts[index] == "skills" and parts[index + 2] == "run":
            return True
    return False


def should_skip_packaged_relpath(
    relpath: str,
    *,
    is_dir: bool,
    skip_skill_runtime_outputs: bool = False,
    skill_runtime_prefixes: tuple[str, ...] = (),
    excluded_relpath_prefixes: tuple[str, ...] = (),
    include_stage_excluded_files: bool = False,
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
    if is_dir:
        if name in STAGE_EXCLUDED_DIRS:
            return True
    elif not include_stage_excluded_files:
        if name in STAGE_EXCLUDED_FILES:
            return True
        if name.lower() in PRIVATE_KEY_FILE_BASENAMES:
            return True
        if any(name.endswith(suffix) for suffix in STAGE_EXCLUDED_SUFFIXES):
            return True
        if any(pattern.match(name) for pattern in STAGE_EXCLUDED_NAME_PATTERNS):
            return True
    if skip_skill_runtime_outputs:
        runtime_parts = [part.lower() for part in pure.parts if part and part != "."]
        if skill_runtime_prefixes:
            normalized_prefix = [part.lower() for part in skill_runtime_prefixes]
            if (
                len(runtime_parts) > len(normalized_prefix)
                and runtime_parts[: len(normalized_prefix)] == normalized_prefix
            ):
                runtime_parts = runtime_parts[len(normalized_prefix) :]
            else:
                runtime_parts = []
        if runtime_parts and _matches_skill_runtime_output_parts(runtime_parts, allow_any_second_part_run=True):
            return True
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
    skip_skill_runtime_outputs: bool = False,
    skill_runtime_prefixes: tuple[str, ...] = (),
    excluded_relpath_prefixes: tuple[str, ...] = (),
    include_stage_excluded_files: bool = False,
) -> bool:
    if _is_local_host_state_path(source_path):
        return True
    return should_skip_packaged_relpath(
        relpath,
        is_dir=is_dir,
        skip_skill_runtime_outputs=skip_skill_runtime_outputs,
        skill_runtime_prefixes=skill_runtime_prefixes,
        excluded_relpath_prefixes=excluded_relpath_prefixes,
        include_stage_excluded_files=include_stage_excluded_files,
    )


def iter_packaged_files(
    root: Path,
    *,
    skip_skill_runtime_outputs: bool = False,
    skill_runtime_prefixes: tuple[str, ...] = (),
    excluded_relpath_prefixes: tuple[str, ...] = (),
    include_stage_excluded_files: bool = False,
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
                skip_skill_runtime_outputs=skip_skill_runtime_outputs,
                skill_runtime_prefixes=skill_runtime_prefixes,
                excluded_relpath_prefixes=excluded_relpath_prefixes,
                include_stage_excluded_files=include_stage_excluded_files,
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
                skip_skill_runtime_outputs=skip_skill_runtime_outputs,
                skill_runtime_prefixes=skill_runtime_prefixes,
                excluded_relpath_prefixes=excluded_relpath_prefixes,
                include_stage_excluded_files=include_stage_excluded_files,
            ):
                continue
            yield current_path / filename


def is_credential_excluded_dir(name: str) -> bool:
    return name in CREDENTIAL_EXCLUDED_DIRS


def matches_workspace_allowlist(
    display_path: str,
    workspace_allowlist: set[str] | None,
    *,
    is_dir: bool | None = None,
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
    "is_credential_excluded_dir",
    "iter_packaged_files",
    "matches_workspace_allowlist",
    "should_skip_packaged_path",
    "should_skip_packaged_relpath",
]
