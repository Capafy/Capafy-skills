from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath

from packaging.common.fs import is_archive_artifact, looks_like_absolute_symlink, relpath


@dataclass(frozen=True)
class FinalZipEntries:

    archive_directories: frozenset[str]
    files_by_archive_path: dict[str, tuple[Path, ...]]
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


def collect_final_zip_entries(
    staging_root: Path,
) -> FinalZipEntries:
    directories: set[str] = set()
    files_by_archive_path: dict[str, list[Path]] = {}
    staging_file_relpaths: set[str] = set()

    for current, dirnames, filenames in os.walk(staging_root, topdown=True):
        current_path = Path(current)
        kept_dirs: list[str] = []
        for dirname in sorted(dirnames):
            directory_path = current_path / dirname
            directory_relpath = relpath(directory_path, staging_root)
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
        staging_file_relpaths=frozenset(staging_file_relpaths),
    )


def final_zip_staging_file_relpaths(
    staging_root: Path,
) -> frozenset[str]:
    return collect_final_zip_entries(staging_root).staging_file_relpaths


__all__ = [
    "FinalZipEntries",
    "archive_parent_dirs",
    "archive_relpath",
    "collect_final_zip_entries",
    "final_zip_staging_file_relpaths",
]
