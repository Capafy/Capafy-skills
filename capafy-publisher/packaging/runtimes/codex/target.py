from __future__ import annotations

from pathlib import Path
from typing import Optional

from packaging._shared.codex.home import resolve_codex_home
from packaging._shared.contracts.stage_plan import StageFileSource, StagePlan, StageTreeSource
from packaging.runtimes.profile_target import EnvProfileTarget


class CodexTarget(EnvProfileTarget):
    _DEFAULT_ENV_ID = "codex"

    def __init__(self, profile: dict):
        super().__init__(profile)
        self.codex_home = resolve_codex_home()

    def confirmed_workspace_document_prefix_roots(self) -> dict[str, Path]:
        return {".codex": self.codex_home}

    def build_stage_plan(self, runtime_dir: str) -> StagePlan:
        plan = super().build_stage_plan(runtime_dir)
        return StagePlan(
            tree_sources=[
                _with_codex_tree_source(source, self.codex_home)
                for source in plan.tree_sources
            ],
            file_sources=[
                _with_codex_file_source(source, self.codex_home)
                for source in plan.file_sources
            ],
            metadata=dict(plan.metadata),
        )


def _codex_target_suffix(relpath: str) -> Optional[str]:
    prefix = ".codex/"
    return relpath[len(prefix) :] if relpath.startswith(prefix) else None


def _with_codex_tree_source(source: StageTreeSource, codex_home: Path) -> StageTreeSource:
    suffix = _codex_target_suffix(source.relative_target_root.as_posix())
    if suffix is None:
        return source
    return StageTreeSource(
        source_root=codex_home / suffix,
        relative_target_root=source.relative_target_root,
        display_prefix=source.display_prefix,
        source_key=source.source_key,
        source_value=source.source_value,
        skip_skill_runtime_outputs=source.skip_skill_runtime_outputs,
        skill_runtime_prefixes=source.skill_runtime_prefixes,
        excluded_relpath_prefixes=source.excluded_relpath_prefixes,
        scan_only=source.scan_only,
        required=source.required,
    )


def _with_codex_file_source(source: StageFileSource, codex_home: Path) -> StageFileSource:
    suffix = _codex_target_suffix(source.relative_target_path.as_posix())
    if suffix is None:
        return source
    return StageFileSource(
        source_file=codex_home / suffix,
        relative_target_path=source.relative_target_path,
        source_key=source.source_key,
        source_value=source.source_value,
        scan_only=source.scan_only,
        required=source.required,
        requires_user_confirmation=source.requires_user_confirmation,
    )


__all__ = ["CodexTarget"]
