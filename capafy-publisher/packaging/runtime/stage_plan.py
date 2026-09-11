from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath
from typing import Optional

from packaging.common.home import safe_expanduser_path
from packaging.common.instruction_docs import is_instruction_doc
from packaging.runtime.profiles import load_profile, string_tuple_profile_value
from packaging.runtime.profiles.path_resolver import resolve_path_spec


@dataclass(frozen=True)
class StageTreeSource:
    source_root: Path
    relative_target_root: Path
    display_prefix: str
    source_key: str
    source_value: str
    skip_skill_runtime_outputs: bool = False
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


class EnvProfileTarget:
    _DEFAULT_ENV_ID = ""

    def __init__(self, profile: Optional[dict] = None):
        merged_profile = load_profile(self._DEFAULT_ENV_ID) if self._DEFAULT_ENV_ID else {}
        if profile:
            merged_profile.update(profile)
        self.profile = merged_profile
        self.env_id = str(merged_profile.get("env_id", self._DEFAULT_ENV_ID))

    def profile_env_id(self) -> Optional[str]:
        return self.env_id or None

    def prepare_runtime_dir(self, runtime_dir: str) -> str:
        return runtime_dir

    def build_stage_plan(self, runtime_dir: str) -> StagePlan:
        return build_stage_plan(self, runtime_dir)

    def discovery_skill_precedence(self) -> tuple[str, ...]:
        return string_tuple_profile_value(self._profile_value("discovery_skill_precedence"))

    def selectable_unit_name(self, unit_path: Path, unit_type: str) -> Optional[str]:
        if unit_type != "skill" or self._profile_value("skill_name_from_directory") is not True:
            return None
        return unit_path.name

    def _profile_value(self, key: str) -> object:
        if key in self.profile:
            return self.profile.get(key)
        if not self.env_id:
            return None
        return load_profile(self.env_id).get(key)

    def validate_runtime(self, runtime_root: Path) -> dict:
        from packaging.runtime.validation import validate_env_runtime

        return validate_env_runtime(
            self.profile,
            runtime_root,
            env_id=self.env_id,
        )


class HomeBackedProfileTarget(EnvProfileTarget):
    _HOME_PREFIX = ""
    _STAGE_PLAN_PREFIXES: tuple[str, ...] = ()

    def __init__(self, profile: Optional[dict] = None):
        super().__init__(profile)
        self.runtime_home = self._resolve_runtime_home()

    def _resolve_runtime_home(self) -> Path:
        raise NotImplementedError

    def confirmed_workspace_document_prefix_roots(self) -> dict[str, Path]:
        return {self._HOME_PREFIX: self.runtime_home}

    def resolve_fixed_scan_file(self, file_spec: dict, *, runtime_dir: Optional[str] = None) -> Path:
        if str(file_spec.get("base", "") or "").strip() != "home":
            return resolve_path_spec(file_spec, runtime_dir=runtime_dir)

        relative = PurePosixPath(str(file_spec.get("path", "") or "").strip())
        if relative.parts and relative.parts[0] == self._HOME_PREFIX:
            relative = PurePosixPath(*relative.parts[1:])
        return self.runtime_home.joinpath(*relative.parts)

    def build_stage_plan(self, runtime_dir: str) -> StagePlan:
        plan = super().build_stage_plan(runtime_dir)
        prefixes = self._STAGE_PLAN_PREFIXES or (self._HOME_PREFIX,)
        return rebase_stage_plan_sources(
            plan,
            source_root=self.runtime_home,
            target_prefixes=prefixes,
        )


def format_source_value(raw: str, workspace_path: Optional[str] = None) -> str:
    if raw == "{workspace_path}":
        if workspace_path is None:
            raise ValueError("workspace_path is required to format source_value")
        return str(safe_expanduser_path(workspace_path).resolve())
    return raw


def _target_suffix(relpath: str, prefixes: tuple[str, ...]) -> Optional[str]:
    normalized_relpath = PurePosixPath(relpath).as_posix().strip("/")
    for raw_prefix in prefixes:
        prefix = PurePosixPath(raw_prefix).as_posix().strip("/")
        if normalized_relpath == prefix:
            return ""
        if normalized_relpath.startswith(f"{prefix}/"):
            return normalized_relpath[len(prefix) + 1 :]
    return None


def rebase_stage_plan_sources(
    plan: StagePlan,
    *,
    source_root: Path,
    target_prefixes: tuple[str, ...],
) -> StagePlan:
    def rebase_tree_source(source: StageTreeSource) -> StageTreeSource:
        suffix = _target_suffix(source.relative_target_root.as_posix(), target_prefixes)
        return (
            replace(source, source_root=source_root / suffix)
            if suffix is not None
            else source
        )

    def rebase_file_source(source: StageFileSource) -> StageFileSource:
        suffix = _target_suffix(source.relative_target_path.as_posix(), target_prefixes)
        return (
            replace(source, source_file=source_root / suffix)
            if suffix is not None
            else source
        )

    return StagePlan(
        tree_sources=[rebase_tree_source(source) for source in plan.tree_sources],
        file_sources=[rebase_file_source(source) for source in plan.file_sources],
        metadata=dict(plan.metadata),
    )


def build_stage_plan(
    target,
    runtime_dir: Optional[str],
) -> StagePlan:
    tree_sources: list[StageTreeSource] = []
    file_sources: list[StageFileSource] = []

    skill_roots = target.profile.get("skill_roots", [])
    if not isinstance(skill_roots, list):
        skill_roots = []
    for root_spec in skill_roots:
        if not isinstance(root_spec, dict):
            continue
        tree_sources.append(
            StageTreeSource(
                source_root=resolve_path_spec(root_spec, runtime_dir=runtime_dir),
                relative_target_root=Path(str(root_spec.get("target_path", ""))),
                display_prefix=str(root_spec.get("display_prefix", "")),
                source_key=str(root_spec.get("source_key", "")),
                source_value=format_source_value(str(root_spec.get("source_value", "copied")), runtime_dir),
                skip_skill_runtime_outputs=bool(root_spec.get("skip_skill_runtime_outputs", False)),
                excluded_relpath_prefixes=string_tuple_profile_value(root_spec.get("excluded_relpath_prefixes")),
                required=False,
            )
        )

    for file_spec in target.profile.get("fixed_scan_files", []):
        if not isinstance(file_spec, dict):
            continue
        display_path = str(file_spec.get("display_path", "")).strip().strip("/")
        if not display_path:
            continue
        normalized_display_path = PurePosixPath(display_path).as_posix()

        if is_instruction_doc(normalized_display_path):
            continue
        file_sources.append(
            StageFileSource(
                source_file=resolve_path_spec(file_spec, runtime_dir=runtime_dir),
                relative_target_path=Path("_scan_only").joinpath(*PurePosixPath(normalized_display_path).parts),
                source_key=str(file_spec.get("display_path", display_path)),
                source_value="scan_only_reference",
                scan_only=True,
                required=False,
            )
        )

    return StagePlan(
        tree_sources=tree_sources,
        file_sources=file_sources,
        metadata={
            "runtime_dir": str(runtime_dir or ""),
        },
    )


__all__ = [
    "EnvProfileTarget",
    "HomeBackedProfileTarget",
    "StageFileSource",
    "StagePlan",
    "StageTreeSource",
    "build_stage_plan",
    "rebase_stage_plan_sources",
]
