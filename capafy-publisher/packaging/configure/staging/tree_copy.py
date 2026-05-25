from __future__ import annotations

from contextlib import suppress
import os
import shutil
from pathlib import Path
from typing import Callable, Optional

from packaging._shared.common.fs import display_stage_path, record_skip, relpath as fs_relpath


SkipPredicate = Callable[[Path, str, bool], bool]
AfterCopyHook = Callable[[Path, Path], None]


_TEXT_CONFIG_SUFFIXES = frozenset(
    {
        ".toml",
        ".env",
        ".json",
        ".yaml",
        ".yml",
        ".txt",
        ".md",
        ".ini",
        ".cfg",
        ".conf",
    }
)


def _is_text_config_file(path: Path) -> bool:
    if path.suffix.lower() in _TEXT_CONFIG_SUFFIXES:
        return True
    return path.name == ".env" or path.name.startswith(".env")


def _normalize_line_endings_if_needed(src: Path, dst: Path) -> bool:
    try:
        raw = src.read_bytes()
        text = raw.decode("utf-8")
    except (UnicodeDecodeError, OSError):
        return False

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if normalized == text:
        return False

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(normalized.encode("utf-8"))
    with suppress(OSError):
        shutil.copystat(src, dst)
    return True


def copy_tree_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_symlink():

        target = os.readlink(src)
        os.symlink(target, dst)
        return
    if _is_text_config_file(src) and _normalize_line_endings_if_needed(src, dst):
        return
    shutil.copy2(src, dst)


def copy_tree(
    source_root: Path,
    target_root: Path,
    display_prefix: str,
    skipped: list[str],
    skipped_seen: set[str],
    *,
    should_skip: SkipPredicate,
    after_copy: Optional[AfterCopyHook] = None,
) -> int:
    copied_files = 0

    for current, dirnames, filenames in os.walk(source_root, topdown=True):
        current_path = Path(current)
        current_relpath = fs_relpath(current_path, source_root)
        target_dir = target_root if current_relpath == "." else target_root / current_relpath

        kept_dirs: list[str] = []
        for dirname in sorted(dirnames):
            relpath = display_stage_path(current_relpath, dirname)
            source_dir = current_path / dirname
            if should_skip(source_dir, relpath, True):
                record_skip(skipped, skipped_seen, display_stage_path(display_prefix, relpath), is_dir=True)
                continue
            kept_dirs.append(dirname)

        dirnames[:] = kept_dirs

        for filename in sorted(filenames):
            relpath = display_stage_path(current_relpath, filename)
            source_file = current_path / filename
            if should_skip(source_file, relpath, False):
                record_skip(skipped, skipped_seen, display_stage_path(display_prefix, relpath))
                continue
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file = target_dir / filename
            copy_tree_file(source_file, target_file)
            if after_copy is not None:
                after_copy(source_file, target_file)
            copied_files += 1

    return copied_files
