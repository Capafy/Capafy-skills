from __future__ import annotations
from typing import Optional

from pathlib import Path, PurePosixPath

from packaging._shared.common.home import safe_expanduser_path
from packaging._shared.contracts.selectable import is_instruction_doc
from packaging._shared.contracts.stage_plan import StageFileSource, StagePlan, StageTreeSource
from packaging._shared.env_profiles import string_tuple_profile_value
from packaging._shared.env_profiles.path_resolver import resolve_path_spec


def iter_tree_root_specs(profile: dict) -> list[dict]:
    specs: list[dict] = []
    for key in ("skill_roots", "asset_roots"):
        value = profile.get(key, [])
        if not isinstance(value, list):
            continue
        specs.extend(spec for spec in value if isinstance(spec, dict))
    return specs


def format_source_value(raw: str, workspace_path: Optional[str] = None) -> str:
    if raw == "{workspace_path}":
        if workspace_path is None:
            raise ValueError("workspace_path is required to format source_value")
        return str(safe_expanduser_path(workspace_path).resolve())
    return raw


def build_stage_plan(
    target,
    runtime_dir: Optional[str],
) -> StagePlan:
    tree_sources: list[StageTreeSource] = []
    file_sources: list[StageFileSource] = []

    for root_spec in iter_tree_root_specs(target.profile):
        tree_sources.append(
            StageTreeSource(
                source_root=resolve_path_spec(root_spec, runtime_dir=runtime_dir),
                relative_target_root=Path(str(root_spec.get("target_path", ""))),
                display_prefix=str(root_spec.get("display_prefix", "")),
                source_key=str(root_spec.get("source_key", "")),
                source_value=format_source_value(str(root_spec.get("source_value", "copied")), runtime_dir),
                skip_skill_runtime_outputs=bool(root_spec.get("skip_skill_runtime_outputs", False)),
                skill_runtime_prefixes=string_tuple_profile_value(root_spec.get("skill_runtime_prefixes")),
                excluded_relpath_prefixes=string_tuple_profile_value(root_spec.get("excluded_relpath_prefixes")),
                required=False,
            )
        )

    for file_spec in target.profile.get("fixed_stage_files", []):
        if not isinstance(file_spec, dict):
            continue
        target_path = str(file_spec.get("target_path", "")).strip()
        file_sources.append(
            StageFileSource(
                source_file=resolve_path_spec(file_spec, runtime_dir=runtime_dir),
                relative_target_path=Path(target_path),
                source_key=str(file_spec.get("source_key", "")),
                source_value=format_source_value(str(file_spec.get("source_value", "copied")), runtime_dir),
                required=False,
                requires_user_confirmation=is_instruction_doc(target_path),
            )
        )

    staged_fixed_paths = {
        PurePosixPath(str(file_spec.get("target_path", "")).strip().strip("/")).as_posix()
        for file_spec in target.profile.get("fixed_stage_files", [])
        if isinstance(file_spec, dict) and str(file_spec.get("target_path", "")).strip()
    }

    for file_spec in target.profile.get("fixed_scan_files", []):
        if not isinstance(file_spec, dict):
            continue
        display_path = str(file_spec.get("display_path", "")).strip().strip("/")
        if not display_path:
            continue
        normalized_display_path = PurePosixPath(display_path).as_posix()


        if normalized_display_path in staged_fixed_paths or is_instruction_doc(normalized_display_path):
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
            "env_id": target.env_id,
            "runtime_dir": str(runtime_dir or ""),
        },
    )


__all__ = [
    "build_stage_plan",
]
