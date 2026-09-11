from __future__ import annotations

import json
from pathlib import Path

from packaging.common.home import safe_expanduser_path

from packaging.runtime.stage_plan import StagePlan, StageTreeSource
from packaging.runtime.plugins.openclaw.workspace_paths import (
    AGENTS_SKILLS_ROOT,
    OPENCLAW_ROOT,
    PACKAGED_WORKSPACE_NAME,
    resolve_openclaw_config_source,
    resolve_openclaw_workspace_runtime_dir,
)


def _collect_extra_skill_dirs(openclaw_root: Path) -> list[Path]:
    config_path = resolve_openclaw_config_source(openclaw_root=openclaw_root)
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


def build_stage_plan(
    runtime_dir: str,
    *,
    openclaw_root: Path = OPENCLAW_ROOT,
    agents_skills_root: Path = AGENTS_SKILLS_ROOT,
) -> StagePlan:
    normalized_runtime_dir = str(runtime_dir or "").strip()
    if not normalized_runtime_dir:
        raise ValueError("runtime_dir is required")

    tree_sources: list[StageTreeSource] = []

    workspace_root = resolve_openclaw_workspace_runtime_dir(normalized_runtime_dir, openclaw_root=openclaw_root)
    tree_sources.append(
        StageTreeSource(
            source_root=workspace_root,
            relative_target_root=Path(".openclaw") / PACKAGED_WORKSPACE_NAME,
            display_prefix=f".openclaw/{PACKAGED_WORKSPACE_NAME}",
            source_key=".openclaw/workspace",
            source_value=PACKAGED_WORKSPACE_NAME,
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

    return StagePlan(
        tree_sources=tree_sources,
        file_sources=[],
    )


__all__ = [
    "build_stage_plan",
]
