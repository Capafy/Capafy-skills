from __future__ import annotations
from typing import Optional

import os
from pathlib import Path

from packaging._shared.common.fs import relpath as fs_relpath
from .support import (
    classify_selectable_directory,
    finalize_selectable_entry,
)
from .unit_metadata import build_unit_metadata


def _iter_skill_dirs(
    staging_root: Path,
    *,
    target=None,
) -> list[tuple[Path, Path, str]]:
    discovered: list[tuple[Path, Path, str]] = []
    seen: set[str] = set()
    for current, dirnames, filenames in os.walk(staging_root, topdown=True):
        current_path = Path(current)
        kept_dirs: list[str] = []
        for dirname in sorted(dirnames):
            skill_dir = current_path / dirname
            relpath = fs_relpath(skill_dir, staging_root)
            selectable_path, unit_type, keep_descending = classify_selectable_directory(
                target,
                skill_dir,
                relpath,
            )
            if selectable_path == relpath and unit_type != "suppressed":
                if relpath not in seen:
                    seen.add(relpath)
                    discovered.append((skill_dir, current_path, unit_type))
                if keep_descending:
                    kept_dirs.append(dirname)
                continue
            if keep_descending:
                kept_dirs.append(dirname)
        dirnames[:] = kept_dirs
    return discovered


def _skill_entry(
    staging_root: Path,
    skill_dir: Path,
    skill_root: Path,
    *,
    unit_type: str = "skill",
    target=None,
) -> tuple[dict, Optional[dict]]:
    relative_path = fs_relpath(skill_dir, staging_root)
    source_root = fs_relpath(skill_root, staging_root)
    meta = build_unit_metadata(
        skill_dir,
        unit_type,
        target=target,
    )

    entry = {
        "path": relative_path,
        "name": meta["name"],
        "description": meta["description"],
        "source_root": source_root,
        "unit_type": unit_type,
        "has_primary_doc": meta["has_primary_doc"],
        "has_skill_md": meta["has_primary_doc"] if unit_type == "skill" else False,
        "file_count": meta["file_count"],
        "size_bytes": meta["size_bytes"],
        "synopsis": meta["synopsis"],
    }
    entry = finalize_selectable_entry(target, entry, unit_path=skill_dir)

    suspicious_entry = None
    if meta["suspicious_reasons"]:
        suspicious_entry = {
            "path": relative_path,
            "name": meta["name"],
            "source_root": source_root,
            "unit_type": unit_type,
            "reasons": meta["suspicious_reasons"],
        }
    return entry, suspicious_entry


def build_skill_inventory(
    staging_root: Path,
    *,
    target=None,
) -> tuple[list[dict], list[dict]]:
    included_skills: list[dict] = []
    suspicious_skills: list[dict] = []
    for skill_dir, skill_root, unit_type in _iter_skill_dirs(
        staging_root,
        target=target,
    ):
        entry, suspicious_entry = _skill_entry(
            staging_root,
            skill_dir,
            skill_root,
            unit_type=unit_type,
            target=target,
        )
        included_skills.append(entry)
        if suspicious_entry is not None:
            suspicious_skills.append(suspicious_entry)
    return included_skills, suspicious_skills
