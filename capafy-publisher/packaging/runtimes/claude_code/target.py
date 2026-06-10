from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Optional

from packaging._shared.contracts.stage_plan import StagePlan
from packaging.runtimes.profile_target import EnvProfileTarget


class ClaudeCodeTarget(EnvProfileTarget):
    _DEFAULT_ENV_ID = "claude_code"

    def finalize_cloud_hosted_packaging(self, staging_root: Path, _stage_plan: StagePlan) -> dict:
        drop_claude_settings_permissions = import_module(
            "packaging.configure.runtimes.claude_code.settings_json"
        ).drop_claude_settings_permissions
        return {
            "claude_code_settings_permissions_removed": drop_claude_settings_permissions(staging_root),
        }

    def selectable_unit_name(self, unit_path: Path, unit_type: str) -> Optional[str]:
        if unit_type != "skill":
            return None
        return unit_path.name

    def collect_special_scan_candidates(
        self,
        path: Path,
        text: str,
        annotate_candidate,
    ) -> tuple[dict[str, str], dict[str, str], dict[str, str], list[dict]]:
        claude_scan_hints = import_module("packaging.configure.runtimes.claude_code.scan_hints")
        if path.name not in claude_scan_hints.CLAUDE_NATIVE_CONFIG_BASENAMES:
            return {}, {}, {}, []
        logical_env_source_path = import_module(
            "packaging.configure.scan.env_scan_rules"
        ).logical_env_source_path
        display_path = path.name
        source_display_path = logical_env_source_path(path, display_path)
        env_hints, val_hints, candidates = claude_scan_hints.collect_claude_json_config_hints(
            text,
            display_path,
            source_display_path,
            annotate_candidate,
        )
        return env_hints, {}, val_hints, candidates

    def should_scan_structured_values(self, relpath: str) -> bool:
        claude_scan_hints = import_module("packaging.configure.runtimes.claude_code.scan_hints")
        return claude_scan_hints.should_scan_claude_structured_values(relpath)


__all__ = [
    "ClaudeCodeTarget",
]
