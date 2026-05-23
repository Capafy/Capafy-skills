from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class StageTreeSource:
    source_root: Path
    relative_target_root: Path
    display_prefix: str
    source_key: str
    source_value: str
    skip_skill_runtime_outputs: bool = False
    skill_runtime_prefixes: tuple[str, ...] = field(default_factory=tuple)
    excluded_relpath_prefixes: tuple[str, ...] = field(default_factory=tuple)
    scan_only: bool = False
    required: bool = True


@dataclass(frozen=True)
class StageFileSource:
    source_file: Path
    relative_target_path: Path
    source_key: str
    source_value: str
    scan_only: bool = False
    required: bool = True
    requires_user_confirmation: bool = False


@dataclass(frozen=True)
class StagePlan:
    tree_sources: list[StageTreeSource]
    file_sources: list[StageFileSource]
    metadata: dict[str, object] = field(default_factory=dict)


__all__ = [
    "StageFileSource",
    "StagePlan",
    "StageTreeSource",
]
