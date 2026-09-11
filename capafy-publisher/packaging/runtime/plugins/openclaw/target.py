from __future__ import annotations
from typing import Optional

from pathlib import Path, PurePosixPath

from packaging.common.home import safe_expanduser_path
from packaging.runtime.stage_plan import EnvProfileTarget, StagePlan
from packaging.runtime.plugins.openclaw import workspace_paths
from packaging.runtime.plugins.openclaw.selection import (
    validate_openclaw_selected_skills,
    canonicalize_openclaw_selection_path,
    normalize_openclaw_selection_groups,
    openclaw_skill_key_from_skill_dir,
)
from packaging.runtime.plugins.openclaw.workspace_paths import (
    AGENTS_SKILLS_ROOT,
    OPENCLAW_ROOT,
)
from packaging.runtime.plugins.openclaw.workspace_plans import (
    build_stage_plan as build_openclaw_stage_plan,
)


_OPENCLAW_WORKSPACE_SOURCE_KEY = ".openclaw/workspace"
_CLOUD_WORKSPACE_EXCLUDED_PREFIXES = (
    ".pytest_cache",
    "dev/tests",
)


class OpenClawTarget(EnvProfileTarget):
    _DEFAULT_ENV_ID = "openclaw"

    def prepare_runtime_dir(self, runtime_dir: str) -> str:
        workspace_root = workspace_paths.resolve_openclaw_workspace_runtime_dir(
            runtime_dir,
            openclaw_root=OPENCLAW_ROOT,
        )
        return str(workspace_root)

    def is_cloud_workspace_source(self, tree_source) -> bool:
        return str(getattr(tree_source, "source_key", "") or "").strip() == _OPENCLAW_WORKSPACE_SOURCE_KEY

    def cloud_workspace_excluded_prefixes(self, tree_source) -> tuple[str, ...]:
        if not self.is_cloud_workspace_source(tree_source):
            return ()
        return _CLOUD_WORKSPACE_EXCLUDED_PREFIXES

    def cloud_workspace_allowlist(self, tree_source, workspace_allowlist):
        if not self.is_cloud_workspace_source(tree_source):
            return None
        return workspace_allowlist

    def build_workspace_allowlist(
        self,
        *,
        stage_plan: StagePlan,
    ) -> Optional[set[str]]:
        for ts in stage_plan.tree_sources:
            if self.is_cloud_workspace_source(ts):
                workspace_root = safe_expanduser_path(ts.source_root)
                if not workspace_root.is_dir():
                    return None
                result = workspace_paths.build_workspace_allowlist(
                    workspace_root,
                    packaged_workspace_prefix=ts.display_prefix,
                    profile=self.profile,
                )
                return result
        return None

    def finalize_selectable_entry(
        self,
        entry: dict,
        *,
        unit_path: Path,
    ) -> dict:
        if str(entry.get("unit_type", "skill")).strip() != "skill":
            return entry
        skill_key = openclaw_skill_key_from_skill_dir(unit_path)
        return {**entry, "skill_key": skill_key} if skill_key else entry

    def validate_selected_skills(
        self,
        *,
        selected_paths: set[str],
        included_skills: list[dict],
    ) -> None:
        validate_openclaw_selected_skills(
            selected_paths=selected_paths,
            included_skills=included_skills,
        )

    def resolve_workspace_reference(self, workspace_name: str) -> Optional[Path]:
        try:
            return workspace_paths.resolve_openclaw_workspace_runtime_dir(
                workspace_name,
                openclaw_root=OPENCLAW_ROOT,
            )
        except ValueError:
            return None

    def confirmed_workspace_document_prefix_roots(self) -> dict[str, Path]:
        return {
            ".openclaw": safe_expanduser_path(OPENCLAW_ROOT),
        }

    def rewrite_confirmed_workspace_document_packaged_path(self, logical_path: str) -> str:
        normalized = PurePosixPath(logical_path.rstrip("/")).as_posix()
        if not normalized:
            return normalized
        pure = PurePosixPath(normalized)
        first_part = pure.parts[0] if pure.parts else ""
        if first_part != "workspace":
            return normalized
        suffix = PurePosixPath(*pure.parts[1:]).as_posix() if len(pure.parts) > 1 else ""
        packaged_root = PurePosixPath(".openclaw") / "workspace"
        return (packaged_root / suffix).as_posix() if suffix else packaged_root.as_posix()

    def canonicalize_selection_path(self, path: str) -> str:
        return canonicalize_openclaw_selection_path(path)

    def normalize_selection_groups(self, selection_groups: dict) -> dict:
        return normalize_openclaw_selection_groups(selection_groups)

    def build_stage_plan(
        self,
        runtime_dir: str,
    ) -> StagePlan:
        return build_openclaw_stage_plan(
            runtime_dir,
            openclaw_root=OPENCLAW_ROOT,
            agents_skills_root=AGENTS_SKILLS_ROOT,
        )

__all__ = [
    "AGENTS_SKILLS_ROOT",
    "OPENCLAW_ROOT",
    "OpenClawTarget",
]
