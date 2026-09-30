from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterator


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
        logical_relpath = _normalized_relpath(getattr(source, "source_key", ""))
        key = (source_file, logical_relpath)
        if source_file.is_file() and logical_relpath and key not in seen:
            seen.add(key)
            yield ScanOnlySourceFile(source_file=source_file, logical_relpath=logical_relpath)

__all__ = ["ScanOnlySourceFile", "iter_scan_only_source_files"]
