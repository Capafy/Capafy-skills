from __future__ import annotations
from typing import Optional

from importlib import import_module
from pathlib import Path, PurePosixPath

from packaging._shared.common.home import safe_expanduser_path
from packaging._shared.contracts.path_shapes import (
    basic_owning_selectable_paths,
    classify_basic_selectable_directory,
    extract_skill_dir_display_path,
)
from packaging._shared.env_profiles import load_profile, string_tuple_profile_value
from packaging.runtimes.openclaw import workspace_paths
from packaging.runtimes.openclaw.selection_paths import (
    canonicalize_openclaw_selection_path,
    normalize_openclaw_selection_groups,
)
from packaging.runtimes.openclaw.workspace_common import (
    AGENTS_SKILLS_ROOT,
    OPENCLAW_EXTENSIONS_DIRNAME,
    OPENCLAW_ROOT,
    OPENCLAW_STAGE_ROOT_FILES,
)
from packaging._shared.runtimes.contracts import CandidateAnnotator, SpecialScanResult
from packaging.runtimes.openclaw import cron_units
from packaging.runtimes.openclaw.selection_units import (
    extract_openclaw_plugin_display_path,
    classify_openclaw_directory_unit,
    finalize_openclaw_selectable_entry,
    infer_openclaw_unit_type_from_path,
    openclaw_owning_selectable_paths,
)
from packaging.runtimes.openclaw.selection_validation import build_openclaw_selection_runtime_validation
from packaging.runtimes.openclaw.workspace_plans import build_stage_plan as build_openclaw_stage_plan
from packaging._shared.runtimes.contracts import OPENCLAW_LEGACY_TARGET, OPENCLAW_MODERN_TARGET
from packaging._shared.contracts.stage_plan import StagePlan


OPENCLAW_CONFIG_MODE_OVERLAY_MERGE = "overlay_merge"
_OPENCLAW_WORKSPACE_SOURCE_KEY = ".openclaw/workspace"
_CLOUD_WORKSPACE_EXCLUDED_PREFIXES = (
    ".pytest_cache",
    "dev/tests",
)


class OpenClawTarget:
    def __init__(self, generation: str):
        self.generation = generation
        self.profile = load_profile("openclaw")

    def profile_env_id(self) -> Optional[str]:
        return "openclaw"

    def prepare_runtime_dir(self, runtime_dir: str) -> str:
        workspace_root = workspace_paths.resolve_openclaw_workspace_runtime_dir(
            runtime_dir,
            openclaw_root=OPENCLAW_ROOT,
        )
        return str(workspace_root)

    def allows_bundle_units(self) -> bool:
        return self.generation == OPENCLAW_MODERN_TARGET

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

    def cloud_workspace_auth_paths(self, stage_plan: StagePlan) -> set[str]:
        runtime_paths: set[str] = set()
        for tree_source in getattr(stage_plan, "tree_sources", []):
            if not self.is_cloud_workspace_source(tree_source):
                continue
            display_prefix = str(getattr(tree_source, "display_prefix", "") or "").strip().rstrip("/")
            if display_prefix:
                runtime_paths.add(f"{display_prefix}/auth-profiles.json")
        return runtime_paths

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
                )
                return result
        return None

    def finalize_selectable_entry(
        self,
        entry: dict,
        *,
        unit_path: Path,
    ) -> dict:
        return finalize_openclaw_selectable_entry(entry, unit_path=unit_path)

    def build_selection_runtime_validation(
        self,
        *,
        selected_paths: set[str],
        included_skills: list[dict],
    ) -> dict:
        return build_openclaw_selection_runtime_validation(
            selected_paths=selected_paths,
            included_skills=included_skills,
        )

    def discover_additional_selectable_units(self) -> list[dict]:
        if not self.allows_bundle_units():
            return []
        return cron_units.discover_openclaw_cron_units(openclaw_root=OPENCLAW_ROOT)

    def augment_stage_plan_for_selected_paths(
        self,
        stage_plan: StagePlan,
        *,
        selected_cron_paths: Optional[set[str]] = None,
    ) -> StagePlan:
        return cron_units.augment_stage_plan_with_selected_cron_jobs(
            stage_plan,
            selected_paths=selected_cron_paths,
            openclaw_root=OPENCLAW_ROOT,
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

    def selected_cron_path_from_selection_item(self, item: dict) -> str:
        cron_id = str(item.get("id", "")).strip()
        if not cron_id:
            return ""
        cron_name = str(item.get("name", "")).strip() or None
        return cron_units.build_openclaw_cron_unit_path(cron_id, job_name=cron_name)

    def looks_like_plugin_related_path(self, display_path: str) -> bool:
        return bool(extract_openclaw_plugin_display_path(display_path))

    def primary_instruction_doc(self, unit_path: Path, unit_type: str) -> Optional[Path]:
        if unit_type != "openclaw_plugin":
            return None
        for filename in ("README.md", "openclaw.plugin.json", "package.json"):
            candidate = unit_path / filename
            if candidate.is_file():
                return candidate
        return None

    def classify_selectable_directory(
        self,
        unit_path: Path,
        display_path: str,
    ) -> tuple[Optional[str], str, bool]:
        if not self.allows_bundle_units():
            return classify_basic_selectable_directory(unit_path, display_path)
        return classify_openclaw_directory_unit(unit_path, display_path)

    def owning_selectable_paths(self, display_path: str) -> tuple[str, ...]:
        if not self.allows_bundle_units():
            return basic_owning_selectable_paths(display_path)
        return openclaw_owning_selectable_paths(display_path)

    def infer_unit_type_from_path(self, display_path: str) -> str:
        if not self.allows_bundle_units():
            return "skill" if extract_skill_dir_display_path(display_path) else "unknown"
        return infer_openclaw_unit_type_from_path(display_path)

    def discovery_skill_precedence(self) -> tuple[str, ...]:
        return string_tuple_profile_value(self.profile.get("discovery_skill_precedence"))

    def collect_special_scan_candidates(
        self,
        path: Path,
        text: str,
        annotate_candidate: CandidateAnnotator,
    ) -> SpecialScanResult:
        openclaw_scan_hints = import_module("packaging.configure.runtimes.openclaw.scan_hints")
        return openclaw_scan_hints.collect_special_scan_candidates(path, text, annotate_candidate)

    def should_scan_structured_values(self, relpath: str) -> bool:
        openclaw_scan_hints = import_module("packaging.configure.runtimes.openclaw.scan_hints")
        return openclaw_scan_hints.should_scan_openclaw_structured_values(relpath)

    def build_stage_plan(
        self,
        runtime_dir: str,
    ) -> StagePlan:
        plan = build_openclaw_stage_plan(
            runtime_dir,
            openclaw_root=OPENCLAW_ROOT,
            agents_skills_root=AGENTS_SKILLS_ROOT,
            stage_root_files=OPENCLAW_STAGE_ROOT_FILES,
            extensions_dirname=OPENCLAW_EXTENSIONS_DIRNAME,
        )
        return StagePlan(
            tree_sources=plan.tree_sources,
            file_sources=plan.file_sources,
            metadata={
                **plan.metadata,
                "env_id": "openclaw",
                "resolved_target": self.generation,
                "runtime_generation": self.generation,
            },
        )

    def finalize_packaging(
        self,
        staging_root: Path,
        stage_plan: StagePlan,
        *,
        agent_type: str = "",
        workspace_documents_manifest_payload: Optional[dict] = None,
    ) -> dict:
        finalize_openclaw_packaging = import_module(
            "packaging.configure.runtimes.openclaw.workspace_postprocess"
        ).postprocess_stage
        return finalize_openclaw_packaging(
            staging_root,
            stage_plan,
            agent_type=agent_type,
            workspace_documents_manifest_payload=workspace_documents_manifest_payload,
        )

    def sync_confirmed_skill_entries(
        self,
        staging_root: Path,
        selection_runtime_validation: Optional[dict],
    ) -> dict[str, int]:
        sync_confirmed_skill_entries_impl = import_module(
            "packaging.configure.runtimes.openclaw.workspace_postprocess"
        ).sync_confirmed_skill_entries
        return sync_confirmed_skill_entries_impl(
            staging_root,
            selection_runtime_validation,
        )

    def collect_runtime_environment_fields(self) -> dict:
        collect_openclaw_runtime_environment_fields = import_module(
            "packaging.configure.runtimes.openclaw.workspace_postprocess"
        ).collect_runtime_environment_fields
        payload = collect_openclaw_runtime_environment_fields()
        payload["openclaw_runtime_generation"] = self.generation
        payload["openclaw_config_mode"] = OPENCLAW_CONFIG_MODE_OVERLAY_MERGE
        return payload

    def validate_runtime(
        self,
        runtime_root: Path,
        *,
        expected_version: Optional[str] = None,
    ) -> dict:
        from packaging.runtimes.validation import validate_env_runtime

        return validate_env_runtime(
            self.profile,
            runtime_root,
            env_id="openclaw",
            expected_version=expected_version,
        )


LEGACY_TARGET = OpenClawTarget(OPENCLAW_LEGACY_TARGET)
MODERN_TARGET = OpenClawTarget(OPENCLAW_MODERN_TARGET)


__all__ = [
    "AGENTS_SKILLS_ROOT",
    "LEGACY_TARGET",
    "MODERN_TARGET",
    "OPENCLAW_EXTENSIONS_DIRNAME",
    "OPENCLAW_ROOT",
    "OPENCLAW_STAGE_ROOT_FILES",
    "OpenClawTarget",
]
