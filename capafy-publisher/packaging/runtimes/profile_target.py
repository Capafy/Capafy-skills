from __future__ import annotations
from typing import Optional

from pathlib import Path
from importlib import import_module

from packaging._shared.contracts.stage_plan import StagePlan
from packaging._shared.env_profiles import load_profile, string_tuple_profile_value
from packaging._shared.runtimes.support import collect_optional_command_first_line
from packaging.runtimes import stage_plan_builder


class EnvProfileTarget:
    _DEFAULT_ENV_ID = ""

    def __init__(self, profile: dict):
        self.profile = profile
        self.env_id = str(profile.get("env_id", self._DEFAULT_ENV_ID))

    def profile_env_id(self) -> Optional[str]:
        return self.env_id or None

    def prepare_runtime_dir(self, runtime_dir: str) -> str:
        return runtime_dir

    def build_stage_plan(self, runtime_dir: str) -> StagePlan:
        return stage_plan_builder.build_stage_plan(self, runtime_dir)

    def finalize_packaging(
        self,
        staging_root: Path,
        stage_plan: StagePlan,
        *,
        agent_type: str = "",
        workspace_documents_manifest_payload: Optional[dict] = None,
    ) -> dict:
        stage_impl = import_module("packaging.configure.staging.env_stage_finalize")
        return stage_impl.finalize_packaging(
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

    def discovery_skill_precedence(self) -> tuple[str, ...]:
        return string_tuple_profile_value(self._profile_value("discovery_skill_precedence"))

    def _profile_value(self, key: str) -> object:
        if key in self.profile:
            return self.profile.get(key)
        if not self.env_id:
            return None
        return load_profile(self.env_id).get(key)

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


__all__ = [
    "EnvProfileTarget",
]
