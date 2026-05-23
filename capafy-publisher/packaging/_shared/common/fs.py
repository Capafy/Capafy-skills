from __future__ import annotations

import errno
import os
import re
import shutil
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable

from .constants import TEXT_ENCODINGS, TEXT_SAMPLE_BYTES, VIRTUALENV_BIN_DIRS, VIRTUALENV_MARKER_FILES
from .exclusion_rules import SYSTEM_DIRS, SYSTEM_SUFFIXES


def _classify_cleanup_error(exc: OSError) -> str:
    if isinstance(exc, PermissionError):
        return "permission_denied"
    if isinstance(exc, FileNotFoundError):
        return "path_missing"
    if isinstance(exc, FileExistsError):
        return "path_conflict"
    if getattr(exc, "errno", None) == errno.ENOSPC:
        return "disk_full"
    return "os_error"


def cleanup_bundle_file(bundle_file: str) -> dict[str, object]:
    summary: dict[str, object] = {}
    normalized_bundle_file = str(bundle_file or "").strip()
    if not normalized_bundle_file:
        return summary

    bundle_path = normalize_path(normalized_bundle_file)
    summary["bundle_path"] = str(bundle_path)
    summary["bundle_removed"] = False
    if not bundle_path.exists():
        return summary
    if not bundle_path.is_file():
        summary["bundle_error"] = f"bundle path is not a file: {bundle_path}"
        summary["bundle_error_kind"] = "path_conflict"
        return summary

    try:
        bundle_path.unlink()
    except OSError as exc:
        summary["bundle_error"] = str(exc)
        summary["bundle_error_kind"] = _classify_cleanup_error(exc)
    else:
        summary["bundle_removed"] = True
    return summary


def cleanup_staging_root(staging_root: str | Path | None) -> dict[str, object]:
    summary: dict[str, object] = {}
    normalized_staging_root = str(staging_root or "").strip()
    if not normalized_staging_root:
        return summary

    staging_path = normalize_path(normalized_staging_root)
    summary["staging_path"] = str(staging_path)
    summary["staging_removed"] = False
    if not staging_path.exists():
        return summary

    try:
        shutil.rmtree(staging_path)
    except OSError as exc:
        summary["staging_error"] = str(exc)
        summary["staging_error_kind"] = _classify_cleanup_error(exc)
    else:
        summary["staging_removed"] = True
    return summary


def safe_chmod(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def normalize_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def relpath(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    if relative == Path("."):
        return "."
    return relative.as_posix()


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def windows_path_parts(rest: str) -> list[str]:
    return [part for part in re.split(r"[\\/]+", rest.strip("\\/")) if part]


def windows_drive_mount_candidates(drive: str) -> list[Path]:
    letter = drive.lower()
    return [Path("/mnt") / letter, Path(f"/{letter}")]


def path_basename(value: str) -> str:
    if re.match(r"^[A-Za-z]:[\\/]", value) or value.startswith("\\\\"):
        return PureWindowsPath(value).name
    if "\\" in value and "/" not in value:
        return PureWindowsPath(value).name
    return PurePosixPath(value).name


def _is_probably_binary(raw: bytes) -> bool:
    sample = raw[:TEXT_SAMPLE_BYTES]
    if not sample:
        return False
    if b"\x00" in sample:
        return True
    printable = 0
    for byte in sample:
        if byte in (9, 10, 13) or 32 <= byte <= 126:
            printable += 1
    return printable / len(sample) < 0.75


def read_text(path: Path) -> tuple[str | None, str | None]:
    try:
        raw = path.read_bytes()
    except OSError:
        return None, None

    sample = raw[:TEXT_SAMPLE_BYTES]
    if b"\x00" in sample:
        return None, None

    for encoding in TEXT_ENCODINGS[:-1]:
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue

    if _is_probably_binary(raw):
        return None, None

    fallback_encoding = TEXT_ENCODINGS[-1]
    try:
        return raw.decode(fallback_encoding), fallback_encoding
    except UnicodeDecodeError:
        return None, None


def record_skip(skipped: list[str], skipped_seen: set[str], relpath: str, is_dir: bool = False) -> None:
    value = relpath.rstrip("/")
    if is_dir:
        value = f"{value}/"
    if value not in skipped_seen:
        skipped.append(value)
        skipped_seen.add(value)


def display_stage_path(prefix: str, relpath: str) -> str:
    if not prefix or prefix == ".":
        return relpath
    if not relpath or relpath == ".":
        return prefix
    return f"{prefix.rstrip('/')}/{relpath}"


def looks_like_virtualenv_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    try:
        child_names = {child.name for child in path.iterdir()}
    except OSError:
        return False
    if not any(marker in child_names for marker in VIRTUALENV_MARKER_FILES):
        return False
    if not any(dirname in child_names for dirname in VIRTUALENV_BIN_DIRS):
        return False
    return True


def is_archive_artifact(name: str) -> bool:
    return name.endswith(".tar.gz") or name.endswith(".zip")


def looks_like_absolute_symlink(path: Path) -> bool:
    if not path.is_symlink():
        return False
    try:
        target = os.readlink(path)
    except OSError:
        return False
    return PurePosixPath(target).is_absolute() or PureWindowsPath(target).is_absolute()


def iter_workspace_files(root: Path, skip_system: bool) -> Iterable[Path]:
    for current, dirnames, filenames in os.walk(root, topdown=True):
        current_path = Path(current)
        kept_dirs: list[str] = []
        for dirname in sorted(dirnames):
            directory_path = current_path / dirname
            if skip_system and (
                dirname in SYSTEM_DIRS or looks_like_virtualenv_dir(directory_path)
            ):
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in sorted(filenames):
            path = current_path / filename
            if skip_system and any(filename.endswith(suffix) for suffix in SYSTEM_SUFFIXES):
                continue
            yield path


__all__ = [
    "cleanup_bundle_file",
    "cleanup_staging_root",
    "display_stage_path",
    "is_archive_artifact",
    "is_within",
    "iter_workspace_files",
    "looks_like_absolute_symlink",
    "looks_like_virtualenv_dir",
    "normalize_path",
    "read_text",
    "record_skip",
    "relpath",
    "safe_chmod",
    "windows_drive_mount_candidates",
    "windows_path_parts",
]
