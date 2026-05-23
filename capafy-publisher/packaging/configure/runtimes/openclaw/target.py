from __future__ import annotations

from pathlib import Path, PurePosixPath

from packaging._shared.common.home import safe_expanduser_path
from packaging._shared.contracts.path_shapes import (
    basic_owning_selectable_paths,
    classify_basic_selectable_directory,
    classify_basic_selectable_file,
    unit_type_from_path,
)
from packaging._shared.env_profiles import load_profile, string_tuple_profile_value
from packaging._shared.openclaw.config import OPENCLAW_CONFIG_MODE_OVERLAY_MERGE
from packaging.configure.runtimes.openclaw import workspace_paths
from packaging.configure.runtimes.openclaw.selection_paths import (
    canonicalize_openclaw_selection_path,
    normalize_openclaw_selection_groups,
)
from packaging.configure.runtimes.openclaw.workspace_common import (
    AGENTS_SKILLS_ROOT,
    OPENCLAW_EXTENSIONS_DIRNAME,
    OPENCLAW_ROOT,
    OPENCLAW_STAGE_ROOT_FILES,
)
from packaging._shared.runtimes.contracts import CandidateAnnotator, SpecialScanResult
from packaging.configure.runtimes.openclaw import cron_units
from packaging.configure.runtimes.openclaw import scan_hints as openclaw_scan_hints
from packaging.configure.runtimes.openclaw.selection_units import (
    extract_openclaw_plugin_display_path,
    build_openclaw_selection_runtime_validation,
    classify_openclaw_directory_unit,
    classify_openclaw_file_unit,
    finalize_openclaw_selectable_entry,
    infer_openclaw_unit_type_from_path,
    openclaw_owning_selectable_paths,
)
from packaging.configure.runtimes.openclaw.workspace_plans import build_stage_plan as build_openclaw_stage_plan
from packaging.configure.runtimes.openclaw.workspace_postprocess import (
    collect_runtime_environment_fields as collect_openclaw_runtime_environment_fields,
    postprocess_stage as finalize_openclaw_packaging,
    sync_confirmed_skill_entries,
)
from packaging.runtimes.resolution import OPENCLAW_LEGACY_TARGET, OPENCLAW_MODERN_TARGET
from packaging._shared.contracts.stage_plan import StagePlan


_OPENCLAW_VALIDATE_PROFILE_PATCH = {
    "fixed_stage_files": [
        {
            "target_path": ".openclaw/openclaw.json",
            "source_value": "copied",
        }
    ],
    "redact_files": [
        {
            "target_path": ".openclaw/openclaw.json",
            "strategy": "json_stage_config",
        }
    ],
}


def build_stage_plan(
    runtime_dir: str,
) -> StagePlan:
    return build_openclaw_stage_plan(
        runtime_dir,
        openclaw_root=OPENCLAW_ROOT,
        agents_skills_root=AGENTS_SKILLS_ROOT,
        stage_root_files=OPENCLAW_STAGE_ROOT_FILES,
        extensions_dirname=OPENCLAW_EXTENSIONS_DIRNAME,
    )


def collect_runtime_environment_fields() -> dict[str, str | None]:
    return collect_openclaw_runtime_environment_fields()


class OpenClawTarget:
    def __init__(self, generation: str):
        self.generation = generation
        self.profile = load_profile("openclaw")

    def profile_env_id(self) -> str | None:
        return "openclaw"

    def prepare_runtime_dir(self, runtime_dir: str) -> str:
        workspace_root = workspace_paths.resolve_openclaw_workspace_runtime_dir(
            runtime_dir,
            openclaw_root=OPENCLAW_ROOT,
        )
        return str(workspace_root)

    def allows_bundle_units(self) -> bool:
        return self.generation == OPENCLAW_MODERN_TARGET

    def build_workspace_allowlist(
        self,
        *,
        stage_plan: StagePlan,
    ) -> set[str] | None:
        for ts in stage_plan.tree_sources:
            if ts.source_key == ".openclaw/workspace":
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
        selected_cron_paths: set[str] | None = None,
    ) -> StagePlan:
        return cron_units.augment_stage_plan_with_selected_cron_jobs(
            stage_plan,
            selected_paths=selected_cron_paths,
            openclaw_root=OPENCLAW_ROOT,
        )

    def resolve_workspace_reference(self, workspace_name: str) -> Path | None:
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

    def primary_instruction_doc(self, unit_path: Path, unit_type: str) -> Path | None:
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
    ) -> tuple[str | None, str, bool]:
        if not self.allows_bundle_units():
            return classify_basic_selectable_directory(unit_path, display_path)
        return classify_openclaw_directory_unit(unit_path, display_path)

    def classify_selectable_file(
        self,
        display_path: str,
    ) -> tuple[str | None, str]:
        if not self.allows_bundle_units():
            return classify_basic_selectable_file(display_path)
        return classify_openclaw_file_unit(display_path)

    def owning_selectable_paths(self, display_path: str) -> tuple[str, ...]:
        if not self.allows_bundle_units():
            return basic_owning_selectable_paths(display_path)
        return openclaw_owning_selectable_paths(display_path)

    def infer_unit_type_from_path(self, display_path: str) -> str:
        if not self.allows_bundle_units():
            return unit_type_from_path(display_path, allow_bundle_units=False)
        return infer_openclaw_unit_type_from_path(display_path)

    def discovery_skill_precedence(self) -> tuple[str, ...]:
        return string_tuple_profile_value(self.profile.get("discovery_skill_precedence"))

    def collect_special_scan_candidates(
        self,
        path: Path,
        text: str,
        annotate_candidate: CandidateAnnotator,
    ) -> SpecialScanResult:
        return openclaw_scan_hints.collect_special_scan_candidates(path, text, annotate_candidate)

    def should_scan_structured_values(self, relpath: str) -> bool:
        return openclaw_scan_hints.should_scan_openclaw_structured_values(relpath)

    def build_stage_plan(
        self,
        runtime_dir: str,
    ) -> StagePlan:
        plan = build_stage_plan(runtime_dir)
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
        workspace_documents_manifest_payload: dict | None = None,
    ) -> dict:
        return finalize_openclaw_packaging(
            staging_root,
            stage_plan,
            agent_type=agent_type,
            workspace_documents_manifest_payload=workspace_documents_manifest_payload,
        )

    def sync_confirmed_skill_entries(
        self,
        staging_root: Path,
        selection_runtime_validation: dict | None,
    ) -> dict[str, int]:
        return sync_confirmed_skill_entries(
            staging_root,
            selection_runtime_validation,
        )

    def collect_runtime_environment_fields(self) -> dict:
        payload = collect_runtime_environment_fields()
        payload["openclaw_runtime_generation"] = self.generation
        payload["openclaw_config_mode"] = OPENCLAW_CONFIG_MODE_OVERLAY_MERGE
        return payload

    def validate_runtime(
        self,
        runtime_root: Path,
        *,
        expected_version: str | None = None,
    ) -> dict:
        from packaging.ship.artifacts.runtimes.env_validate import validate_env_runtime

        validate_profile = {
            **self.profile,
            **_OPENCLAW_VALIDATE_PROFILE_PATCH,
        }
        return validate_env_runtime(
            validate_profile,
            runtime_root,
            env_id="openclaw",
            expected_version=expected_version,
        )


LEGACY_TARGET = OpenClawTarget(OPENCLAW_LEGACY_TARGET)
MODERN_TARGET = OpenClawTarget(OPENCLAW_MODERN_TARGET)
TARGET = MODERN_TARGET


__all__ = [
    "AGENTS_SKILLS_ROOT",
    "LEGACY_TARGET",
    "MODERN_TARGET",
    "OPENCLAW_EXTENSIONS_DIRNAME",
    "OPENCLAW_ROOT",
    "OPENCLAW_STAGE_ROOT_FILES",
    "OpenClawTarget",
    "TARGET",
    "build_stage_plan",
    "collect_runtime_environment_fields",
]
