from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

from packaging._shared.common.home import safe_expanduser_path
from packaging._shared.contracts.selectable import is_instruction_doc
from packaging._shared.env_profiles import load_profile
from packaging._shared.env_profiles.path_resolver import resolve_path_spec

from packaging._shared.contracts.stage_plan import StageFileSource, StagePlan, StageTreeSource
from packaging.configure.runtimes.openclaw.workspace_common import (
    AGENTS_SKILLS_ROOT,
    OPENCLAW_EXTENSIONS_DIRNAME,
    OPENCLAW_ROOT,
    OPENCLAW_STAGE_ROOT_FILES,
)
from packaging.configure.runtimes.openclaw.workspace_paths import (
    packaged_workspace_name,
    resolve_openclaw_workspace_runtime_dir,
)


def _collect_extra_skill_dirs(openclaw_root: Path) -> list[Path]:
    config_path = safe_expanduser_path(openclaw_root / "openclaw.json")
    if not config_path.is_file():
        return []
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    skills_section = payload.get("skills")
    if not isinstance(skills_section, dict):
        return []
    load_section = skills_section.get("load")
    if not isinstance(load_section, dict):
        return []
    extra_dirs = load_section.get("extraDirs")
    if not isinstance(extra_dirs, list):
        return []
    result = []
    for item in extra_dirs:
        normalized = str(item or "").strip()
        if not normalized:
            continue
        candidate = safe_expanduser_path(normalized)
        if candidate.is_dir():
            result.append(candidate.resolve())
    return result


def _fixed_scan_file_sources(openclaw_root: Path, workspace_root: Path) -> list[StageFileSource]:
    file_sources: list[StageFileSource] = []
    profile = load_profile("openclaw")
    home_root = safe_expanduser_path(openclaw_root).parent
    for file_spec in profile.get("fixed_scan_files", []):
        if not isinstance(file_spec, dict):
            continue
        display_path = str(file_spec.get("display_path", "")).strip().strip("/")
        if not display_path:
            continue
        if is_instruction_doc(display_path):
            continue
        display_parts = PurePosixPath(display_path).parts
        file_sources.append(
            StageFileSource(
                source_file=resolve_path_spec(
                    file_spec,
                    home=home_root,
                    runtime_dir=str(workspace_root),
                ),
                relative_target_path=Path("_scan_only").joinpath(*display_parts),
                source_key=display_path,
                source_value="scan_only_reference",
                scan_only=True,
                required=False,
            )
        )
    return file_sources


def build_stage_plan(
    runtime_dir: str,
    *,
    openclaw_root: Path = OPENCLAW_ROOT,
    agents_skills_root: Path = AGENTS_SKILLS_ROOT,
    stage_root_files: tuple[str, ...] = OPENCLAW_STAGE_ROOT_FILES,
    extensions_dirname: str = OPENCLAW_EXTENSIONS_DIRNAME,
) -> StagePlan:
    normalized_runtime_dir = str(runtime_dir or "").strip()
    if not normalized_runtime_dir:
        raise ValueError("runtime_dir is required")

    tree_sources: list[StageTreeSource] = []
    file_sources: list[StageFileSource] = []

    workspace_root = resolve_openclaw_workspace_runtime_dir(normalized_runtime_dir, openclaw_root=openclaw_root)
    normalized_packaged_workspace_name = packaged_workspace_name(
        normalized_runtime_dir,
        openclaw_root=openclaw_root,
    )
    tree_sources.append(
        StageTreeSource(
            source_root=workspace_root,
            relative_target_root=Path(".openclaw") / normalized_packaged_workspace_name,
            display_prefix=f".openclaw/{normalized_packaged_workspace_name}",
            source_key=".openclaw/workspace",
            source_value=normalized_packaged_workspace_name,
        )
    )
    for filename in stage_root_files:
        file_sources.append(
            StageFileSource(
                source_file=safe_expanduser_path(openclaw_root / filename),
                relative_target_path=Path(".openclaw") / filename,
                source_key=f".openclaw/{filename}",
                source_value="copied",
            )
        )

    tree_sources.append(
        StageTreeSource(
            source_root=safe_expanduser_path(openclaw_root / "skills"),
            relative_target_root=Path(".openclaw") / "skills",
            display_prefix=".openclaw/skills",
            source_key=".openclaw/skills",
            source_value="copied",
            skip_skill_runtime_outputs=True,
            required=False,
        )
    )
    extensions_root = safe_expanduser_path(openclaw_root / extensions_dirname)
    if extensions_root.is_dir():
        tree_sources.append(
            StageTreeSource(
                source_root=extensions_root,
                relative_target_root=Path(".openclaw") / extensions_dirname,
                display_prefix=".openclaw/extensions",
                source_key=".openclaw/extensions",
                source_value="copied",
                skip_skill_runtime_outputs=True,
            )
        )

    tree_sources.append(
        StageTreeSource(
            source_root=safe_expanduser_path(agents_skills_root),
            relative_target_root=Path(".agents") / "skills",
            display_prefix=".agents/skills",
            source_key=".agents/skills",
            source_value="copied",
            skip_skill_runtime_outputs=True,
            required=False,
        )
    )

    for extra_dir in _collect_extra_skill_dirs(openclaw_root):
        display = f".openclaw/extra-skills/{extra_dir.name}"
        tree_sources.append(
            StageTreeSource(
                source_root=extra_dir,
                relative_target_root=Path(".openclaw") / "extra-skills" / extra_dir.name,
                display_prefix=display,
                source_key=display,
                source_value="extra_skill_dir",
                skip_skill_runtime_outputs=True,
            )
        )

    file_sources.extend(_fixed_scan_file_sources(openclaw_root, workspace_root))

    return StagePlan(
        tree_sources=tree_sources,
        file_sources=file_sources,
    )


__all__ = [
    "build_stage_plan",
]
