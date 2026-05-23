from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

from packaging._shared.common.fs import (
    display_stage_path,
    looks_like_absolute_symlink,
    looks_like_virtualenv_dir,
    relpath as fs_relpath,
)
from packaging._shared.common.packaged_files import should_skip_packaged_relpath
from packaging.configure.selection.support import (
    build_unit_metadata,
    classify_selectable_directory,
    classify_selectable_file,
    finalize_selectable_entry,
)
from packaging._shared.contracts.path_shapes import basic_allowed_skill_root_prefixes
from packaging._shared.contracts.stage_plan import StagePlan, StageTreeSource
from packaging._shared.runtimes.contracts import call_optional_target_hook


def _allowed_skill_root_prefixes(target, display_prefix: str) -> set[str]:
    return set(
        call_optional_target_hook(
            target,
            "allowed_skill_root_prefixes",
            display_prefix,
            default=basic_allowed_skill_root_prefixes(display_prefix),
        )
    )


def _skill_root_prefix(path: object) -> str:
    normalized = PurePosixPath(str(path or "").strip().rstrip("/")).as_posix()
    if not normalized or normalized == ".":
        return ""
    parts = [part for part in PurePosixPath(normalized).parts if part and part != "."]
    for index, part in enumerate(parts):
        if part == "skills":
            return PurePosixPath(*parts[: index + 1]).as_posix()
    return ""


def _build_discovered_entry(
    unit_path: Path,
    display_path: str,
    source_root_display: str,
    *,
    discovery_root: str,
    unit_type: str,
    target=None,
) -> dict:
    meta = build_unit_metadata(unit_path, unit_type, target=target)
    entry = {
        "path": display_path,
        "name": meta["name"],
        "description": meta["description"],
        "source_root": source_root_display,
        "discovery_root": discovery_root,
        "unit_type": unit_type,
        "has_primary_doc": meta["has_primary_doc"],
        "has_skill_md": meta["has_primary_doc"] if unit_type == "skill" else False,
        "file_count": meta["file_count"],
        "size_bytes": meta["size_bytes"],
        "synopsis": meta["synopsis"],
        "suspicious_reasons": meta["suspicious_reasons"],
    }
    if unit_type == "skill":
        entry["source_path"] = str(unit_path.expanduser().resolve(strict=False))
        entry["binding_kind"] = "workspace_skill_dir"
    return finalize_selectable_entry(target, entry, unit_path=unit_path)


def _discovery_root_for_tree_source(tree_source: StageTreeSource) -> str:
    raw = str(getattr(tree_source, "source_key", "")).strip().rstrip("/")
    if raw:
        normalized = PurePosixPath(raw).as_posix()
        return "" if normalized == "." else normalized
    return ""


def _append_discovered_entry(
    discovered: list[dict],
    seen: set[tuple[str, str]],
    *,
    unit_path: Path,
    display_path: str,
    display_prefix: str,
    discovery_root: str,
    unit_type: str,
    target=None,
) -> None:
    dedupe_key = (display_path, discovery_root)
    if dedupe_key in seen:
        return
    discovered.append(
        _build_discovered_entry(
            unit_path,
            display_path,
            display_prefix,
            discovery_root=discovery_root,
            unit_type=unit_type,
            target=target,
        )
    )
    seen.add(dedupe_key)


def _iter_tree_source_units(
    tree_source: StageTreeSource,
    *,
    target=None,
) -> list[dict]:
    source_root = tree_source.source_root.expanduser()
    if not source_root.is_dir():
        return []

    display_prefix = str(tree_source.display_prefix).strip().rstrip("/")
    allowed_skill_roots = _allowed_skill_root_prefixes(target, display_prefix)
    discovery_root = _discovery_root_for_tree_source(tree_source)
    discovered: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for current, dirnames, filenames in os.walk(source_root, topdown=True):
        current_path = Path(current)
        current_relpath = fs_relpath(current_path, source_root)
        kept_dirs: list[str] = []

        for dirname in sorted(dirnames):
            candidate_path = current_path / dirname
            relpath = display_stage_path(current_relpath, dirname)
            display_path = display_stage_path(display_prefix, relpath)
            skill_root_path = _skill_root_prefix(display_path)

            selectable_path, unit_type, keep_descending = classify_selectable_directory(
                target,
                candidate_path,
                display_path,
            )

            if looks_like_virtualenv_dir(candidate_path):
                continue

            if looks_like_absolute_symlink(candidate_path):

                if selectable_path == display_path and unit_type != "suppressed" and candidate_path.exists():
                    _append_discovered_entry(
                        discovered,
                        seen,
                        unit_path=candidate_path,
                        display_path=display_path,
                        display_prefix=display_prefix,
                        discovery_root=discovery_root,
                        unit_type=unit_type,
                        target=target,
                    )
                continue

            if should_skip_packaged_relpath(
                relpath,
                is_dir=True,
                skip_skill_runtime_outputs=tree_source.skip_skill_runtime_outputs,
                skill_runtime_prefixes=tree_source.skill_runtime_prefixes,
                excluded_relpath_prefixes=tree_source.excluded_relpath_prefixes,
            ):
                continue

            if allowed_skill_roots and skill_root_path and skill_root_path not in allowed_skill_roots:
                continue

            if selectable_path == display_path and unit_type != "suppressed":
                _append_discovered_entry(
                    discovered,
                    seen,
                    unit_path=candidate_path,
                    display_path=display_path,
                    display_prefix=display_prefix,
                    discovery_root=discovery_root,
                    unit_type=unit_type,
                    target=target,
                )

                if keep_descending:
                    kept_dirs.append(dirname)
                continue

            if keep_descending:
                kept_dirs.append(dirname)

        dirnames[:] = kept_dirs

        for filename in sorted(filenames):
            source_file = current_path / filename
            relpath = display_stage_path(current_relpath, filename)
            display_path = display_stage_path(display_prefix, relpath)
            skill_root_path = _skill_root_prefix(display_path)
            selectable_path, unit_type = classify_selectable_file(
                target,
                display_path,
            )

            if looks_like_absolute_symlink(source_file):
                if selectable_path == display_path and source_file.exists():
                    _append_discovered_entry(
                        discovered,
                        seen,
                        unit_path=source_file,
                        display_path=display_path,
                        display_prefix=display_prefix,
                        discovery_root=discovery_root,
                        unit_type=unit_type,
                        target=target,
                    )
                continue

            if should_skip_packaged_relpath(
                relpath,
                is_dir=False,
                skip_skill_runtime_outputs=tree_source.skip_skill_runtime_outputs,
                skill_runtime_prefixes=tree_source.skill_runtime_prefixes,
                excluded_relpath_prefixes=tree_source.excluded_relpath_prefixes,
            ):
                continue

            if allowed_skill_roots and skill_root_path and skill_root_path not in allowed_skill_roots:
                continue

            if selectable_path == display_path:
                _append_discovered_entry(
                    discovered,
                    seen,
                    unit_path=source_file,
                    display_path=display_path,
                    display_prefix=display_prefix,
                    discovery_root=discovery_root,
                    unit_type=unit_type,
                    target=target,
                )

    return discovered


def _normalize_additional_entry(entry: dict) -> dict:
    payload = dict(entry)
    payload.setdefault("description", "")
    payload.setdefault("synopsis", "")
    payload.setdefault("has_primary_doc", False)
    payload.setdefault("has_skill_md", False)
    payload.setdefault("file_count", 0)
    payload.setdefault("size_bytes", 0)
    payload.setdefault("suspicious_reasons", [])
    return payload


def discover_units(
    stage_plan: StagePlan,
    *,
    target=None,
) -> tuple[list[dict], list[dict]]:
    discovered: list[dict] = []
    suspicious: list[dict] = []
    seen_units: set[tuple[str, str]] = set()

    for tree_source in stage_plan.tree_sources:
        for entry in _iter_tree_source_units(tree_source, target=target):
            path = str(entry.get("path", "")).strip()
            discovery_root = str(entry.get("discovery_root", "")).strip()
            dedupe_key = (path, discovery_root)
            if not path or dedupe_key in seen_units:
                continue
            seen_units.add(dedupe_key)
            discovered.append(entry)
            if entry.get("suspicious_reasons"):
                suspicious.append(entry)

    extra_entries = call_optional_target_hook(
        target,
        "discover_additional_selectable_units",
        default=[],
    )
    for raw_entry in extra_entries:
        path = str(raw_entry.get("path", "")).strip()
        discovery_root = str(raw_entry.get("discovery_root", raw_entry.get("source_root", ""))).strip()
        dedupe_key = (path, discovery_root)
        if not path or dedupe_key in seen_units:
            continue
        entry = _normalize_additional_entry(raw_entry)
        seen_units.add(dedupe_key)
        discovered.append(entry)
        if entry.get("suspicious_reasons"):
            suspicious.append(entry)

    discovered.sort(key=lambda item: (str(item.get("path", "")), str(item.get("discovery_root", ""))))
    suspicious.sort(key=lambda item: (str(item.get("path", "")), str(item.get("discovery_root", ""))))
    return discovered, suspicious


__all__ = [
    "discover_units",
]
