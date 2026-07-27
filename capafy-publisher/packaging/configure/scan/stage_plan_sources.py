from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterator, Optional


@dataclass(frozen=True)
class ScanOnlySourceFile:
    source_file: Path
    logical_relpath: str


def _normalized_relpath(value: object) -> str:
    normalized = str(value or "").strip().replace("\\", "/").strip("/")
    if not normalized:
        return ""
    return PurePosixPath(normalized).as_posix()


def iter_scan_only_source_files(stage_plan) -> Iterator[ScanOnlySourceFile]:
    seen: set[tuple[Path, str]] = set()
    for source in getattr(stage_plan, "file_sources", []):
        if not getattr(source, "scan_only", False):
            continue
        source_file = Path(getattr(source, "source_file", Path(""))).expanduser()
        logical_relpath = _normalized_relpath(getattr(source, "relative_target_path", ""))
        key = (source_file, logical_relpath)
        if source_file.is_file() and logical_relpath and key not in seen:
            seen.add(key)
            yield ScanOnlySourceFile(source_file=source_file, logical_relpath=logical_relpath)

    for source in getattr(stage_plan, "tree_sources", []):
        if not getattr(source, "scan_only", False):
            continue
        source_root = Path(getattr(source, "source_root", Path(""))).expanduser()
        target_root = _normalized_relpath(getattr(source, "relative_target_root", ""))
        if not source_root.is_dir() or not target_root:
            continue
        for source_file in sorted(path for path in source_root.rglob("*") if path.is_file()):
            try:
                suffix = source_file.relative_to(source_root).as_posix()
            except ValueError:
                continue
            logical_relpath = f"{target_root}/{suffix}" if suffix else target_root
            key = (source_file, logical_relpath)
            if key in seen:
                continue
            seen.add(key)
            yield ScanOnlySourceFile(source_file=source_file, logical_relpath=logical_relpath)


def resolve_scan_only_source_file(stage_plan, *relpaths: str) -> Optional[Path]:
    candidates = {_normalized_relpath(value) for value in relpaths if _normalized_relpath(value)}
    if not candidates:
        return None
    expanded = set(candidates)
    expanded.update(
        f"_scan_only/{value}"
        for value in candidates
        if not value.startswith("_scan_only/")
    )
    for item in iter_scan_only_source_files(stage_plan):
        if item.logical_relpath in expanded:
            return item.source_file
    return None


def scan_only_source_files_under(stage_plan, relpath: str) -> list[Path]:
    normalized = _normalized_relpath(relpath)
    prefixes = {normalized}
    if normalized and not normalized.startswith("_scan_only/"):
        prefixes.add(f"_scan_only/{normalized}")
    result: list[Path] = []
    for item in iter_scan_only_source_files(stage_plan):
        if any(
            item.logical_relpath == prefix or item.logical_relpath.startswith(f"{prefix}/")
            for prefix in prefixes
            if prefix
        ):
            result.append(item.source_file)
    return result


__all__ = [
    "ScanOnlySourceFile",
    "iter_scan_only_source_files",
    "resolve_scan_only_source_file",
    "scan_only_source_files_under",
]
