from __future__ import annotations
from typing import Optional

from importlib import import_module
from pathlib import Path

from packaging._shared.contracts.stage_plan import StageFileSource, StagePlan, StageTreeSource
from packaging._shared.env_profiles import string_tuple_profile_value
from packaging._shared.env_profiles import load_profile
from packaging._shared.runtimes.support import collect_optional_command_first_line
from packaging.runtimes import stage_plan_builder
from packaging.runtimes.hermes.config import resolve_hermes_home


_HERMES_EXCLUDED_PREFIXES = (
    "sessions",
    "memories",
    "logs",
    "credentials",
    "oauth",
    "auth",
    "worktrees",
)
_HERMES_SCAN_ONLY_FILES = (
    ".anthropic_oauth.json",
    "auth/google_oauth.json",
    "auth.json",
)


class HermesTarget:
    _DEFAULT_ENV_ID = "hermes"

    def __init__(self, profile: Optional[dict] = None):
        if _is_loaded_profile(profile):
            merged_profile = dict(profile)
        else:
            merged_profile = load_profile("hermes")
        if profile and not _is_loaded_profile(profile):
            merged_profile.update(profile)
        self.profile = merged_profile
        self.env_id = str(merged_profile.get("env_id", self._DEFAULT_ENV_ID))
        self.hermes_home = resolve_hermes_home()

    def profile_env_id(self) -> Optional[str]:
        return self.env_id or None

    def prepare_runtime_dir(self, runtime_dir: str) -> str:
        return runtime_dir

    def confirmed_workspace_document_prefix_roots(self) -> dict[str, Path]:
        return {
            ".hermes": self.hermes_home,
        }

    def build_stage_plan(self, runtime_dir: str) -> StagePlan:
        plan = stage_plan_builder.build_stage_plan(self, runtime_dir)
        hermes_home = self.hermes_home
        scan_only_sources = [
            StageTreeSource(
                source_root=hermes_home / rel,
                relative_target_root=Path("_scan_only") / ".hermes" / rel,
                display_prefix=f"_scan_only/.hermes/{rel}",
                source_key=f"_scan_only/.hermes/{rel}",
                source_value="scan_only_reference",
                scan_only=True,
                required=False,
            )
            for rel in ("credentials", "oauth")
        ]
        scan_only_files = [
            StageFileSource(
                source_file=hermes_home / rel,
                relative_target_path=Path("_scan_only") / ".hermes" / rel,
                source_key=f"_scan_only/.hermes/{rel}",
                source_value="scan_only_reference",
                scan_only=True,
                required=False,
            )
            for rel in _HERMES_SCAN_ONLY_FILES
        ]
        packaged_sources = [
            _with_hermes_tree_source(source, hermes_home)
            for source in plan.tree_sources
        ]
        file_sources = [
            _with_hermes_file_source(source, hermes_home)
            for source in plan.file_sources
        ]
        return StagePlan(
            tree_sources=[*packaged_sources, *scan_only_sources],
            file_sources=[*file_sources, *scan_only_files],
            metadata={
                **plan.metadata,
                "env_id": "hermes",
                "hermes_home": str(hermes_home.resolve()),
                "runtime_generation": "hermes_v1",
            },
        )

    def discovery_skill_precedence(self) -> tuple[str, ...]:
        return string_tuple_profile_value(self.profile.get("discovery_skill_precedence"))

    def finalize_packaging(
        self,
        staging_root: Path,
        stage_plan: StagePlan,
        *,
        agent_type: str = "",
        workspace_documents_manifest_payload: Optional[dict] = None,
    ) -> dict:
        _ = workspace_documents_manifest_payload
        stage_finalize = import_module("packaging.configure.staging.env_stage_finalize")
        return stage_finalize.finalize_packaging(
            self,
            staging_root,
            stage_plan,
            agent_type=agent_type,
        )

    def collect_runtime_environment_fields(self) -> dict:
        runtime_env = self.profile.get("runtime_env", {})
        if not isinstance(runtime_env, dict):
            return {}
        field = runtime_env.get("field")
        command = runtime_env.get("command")
        if not field or not isinstance(command, list) or not command:
            return {}
        return {str(field): collect_optional_command_first_line([str(item) for item in command])}

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
            env_id=self.env_id,
            expected_version=expected_version,
        )

    def should_scan_structured_values(self, relpath: str) -> bool:
        normalized = str(relpath or "").strip().replace("\\", "/")
        return normalized not in {
            ".hermes/config.yaml",
            "_scan_only/.hermes/config.yaml",
        }


def _is_loaded_profile(profile: Optional[dict]) -> bool:
    return isinstance(profile, dict) and "env_id" in profile and "runtime_env" in profile


def _with_hermes_exclusions(source: StageTreeSource) -> StageTreeSource:
    if not _targets_packaged_hermes_root(source.relative_target_root):
        return source
    existing = tuple(source.excluded_relpath_prefixes)
    merged = tuple(dict.fromkeys([*existing, *_HERMES_EXCLUDED_PREFIXES]))
    return StageTreeSource(
        source_root=source.source_root,
        relative_target_root=source.relative_target_root,
        display_prefix=source.display_prefix,
        source_key=source.source_key,
        source_value=source.source_value,
        skip_skill_runtime_outputs=source.skip_skill_runtime_outputs,
        skill_runtime_prefixes=source.skill_runtime_prefixes,
        excluded_relpath_prefixes=merged,
        scan_only=source.scan_only,
        required=source.required,
    )


def _with_hermes_tree_source(source: StageTreeSource, hermes_home: Path) -> StageTreeSource:
    source = _with_hermes_exclusions(source)
    suffix = _hermes_target_suffix(source.relative_target_root.as_posix())
    if suffix is None:
        return source
    return StageTreeSource(
        source_root=hermes_home / suffix,
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


def _with_hermes_file_source(source: StageFileSource, hermes_home: Path) -> StageFileSource:
    suffix = _hermes_target_suffix(source.relative_target_path.as_posix())
    if suffix is None:
        return source
    return StageFileSource(
        source_file=hermes_home / suffix,
        relative_target_path=source.relative_target_path,
        source_key=source.source_key,
        source_value=source.source_value,
        scan_only=source.scan_only,
        required=source.required,
        requires_user_confirmation=source.requires_user_confirmation,
    )


def _hermes_target_suffix(relpath: str) -> Optional[str]:
    for prefix in (".hermes/", "_scan_only/.hermes/"):
        if relpath.startswith(prefix):
            return relpath[len(prefix) :]
    return None


def _targets_packaged_hermes_root(relpath: Path) -> bool:
    parts = relpath.parts
    return bool(parts) and parts[0] == ".hermes"


__all__ = [
    "HermesTarget",
]
