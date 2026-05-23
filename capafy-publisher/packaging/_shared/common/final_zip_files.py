from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath

from packaging._shared.common.fs import is_archive_artifact, looks_like_absolute_symlink, relpath


@dataclass(frozen=True)
class FinalZipEntries:

    archive_directories: frozenset[str]
    files_by_archive_path: dict[str, tuple[Path, ...]]
    archive_file_relpaths: frozenset[str]
    staging_file_relpaths: frozenset[str]


def archive_relpath(staging_relpath: str) -> str:
    normalized = PurePosixPath(str(staging_relpath or "").replace("\\", "/")).as_posix().lstrip("/")
    if normalized == "workspace":
        return ""
    if normalized.startswith("workspace/"):
        return normalized[len("workspace/") :]
    return normalized


def archive_parent_dirs(archive_path: str) -> set[str]:
    parts = PurePosixPath(archive_path).parts[:-1]
    return {
        PurePosixPath(*parts[:index]).as_posix()
        for index in range(1, len(parts) + 1)
    }


def _normalize_excluded_path(value: object) -> str:
    normalized = str(value or "").strip().replace("\\", "/").rstrip("/")
    if not normalized:
        return ""
    normalized = PurePosixPath(normalized).as_posix().lstrip("/")
    if normalized in ("", "."):
        return ""
    return normalized


def _is_excluded_prefix(relpath: str, excluded_prefixes: tuple[str, ...]) -> bool:
    return any(relpath == prefix or relpath.startswith(prefix + "/") for prefix in excluded_prefixes)


def collect_final_zip_entries(
    staging_root: Path,
    *,
    exclude_paths: set[str] | None = None,
    exclude_prefixes: tuple[str, ...] = (),
) -> FinalZipEntries:
    directories: set[str] = set()
    files_by_archive_path: dict[str, list[Path]] = {}
    staging_file_relpaths: set[str] = set()
    excluded = {
        normalized
        for normalized in (_normalize_excluded_path(item) for item in (exclude_paths or set()))
        if normalized
    }
    excluded_prefixes = tuple(
        dict.fromkeys(
            normalized
            for normalized in (_normalize_excluded_path(item) for item in exclude_prefixes)
            if normalized
        )
    )

    for current, dirnames, filenames in os.walk(staging_root, topdown=True):
        current_path = Path(current)
        kept_dirs: list[str] = []
        for dirname in sorted(dirnames):
            directory_path = current_path / dirname
            directory_relpath = relpath(directory_path, staging_root)
            if directory_relpath in excluded:
                continue
            if _is_excluded_prefix(directory_relpath, excluded_prefixes):
                continue
            if looks_like_absolute_symlink(directory_path):
                continue
            kept_dirs.append(dirname)
            archive_dir = archive_relpath(directory_relpath)
            if archive_dir:
                directories.add(archive_dir)
        dirnames[:] = kept_dirs

        for filename in sorted(filenames):
            file_path = current_path / filename
            file_relpath = relpath(file_path, staging_root)
            if file_relpath in excluded:
                continue
            if _is_excluded_prefix(file_relpath, excluded_prefixes):
                continue
            if looks_like_absolute_symlink(file_path):
                continue
            if is_archive_artifact(filename):
                continue
            archive_path = archive_relpath(file_relpath)
            if not archive_path:
                continue
            directories.update(archive_parent_dirs(archive_path))
            files_by_archive_path.setdefault(archive_path, []).append(file_path)
            staging_file_relpaths.add(file_relpath)

    final_files_by_archive_path = {
        archive_path: tuple(paths)
        for archive_path, paths in files_by_archive_path.items()
    }
    return FinalZipEntries(
        archive_directories=frozenset(directories),
        files_by_archive_path=final_files_by_archive_path,
        archive_file_relpaths=frozenset(final_files_by_archive_path),
        staging_file_relpaths=frozenset(staging_file_relpaths),
    )


def final_zip_staging_file_relpaths(
    staging_root: Path,
    *,
    exclude_paths: set[str] | None = None,
    exclude_prefixes: tuple[str, ...] = (),
) -> frozenset[str]:
    return collect_final_zip_entries(
        staging_root,
        exclude_paths=exclude_paths,
        exclude_prefixes=exclude_prefixes,
    ).staging_file_relpaths


__all__ = [
    "FinalZipEntries",
    "archive_parent_dirs",
    "archive_relpath",
    "collect_final_zip_entries",
    "final_zip_staging_file_relpaths",
]
