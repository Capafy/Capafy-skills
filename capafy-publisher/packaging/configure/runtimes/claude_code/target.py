from __future__ import annotations

from pathlib import Path
from typing import Optional

from packaging.configure.runtimes.env_profile_target import EnvProfileTarget
from packaging.configure.runtimes.claude_code import scan_hints as claude_scan_hints
from packaging.configure.scan.env_scan_rules import logical_env_source_path


class ClaudeCodeTarget(EnvProfileTarget):
    _DEFAULT_ENV_ID = "claude_code"

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
        if path.name not in claude_scan_hints.CLAUDE_NATIVE_CONFIG_BASENAMES:
            return {}, {}, {}, []
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
        return claude_scan_hints.should_scan_claude_structured_values(relpath)


__all__ = [
    "ClaudeCodeTarget",
]
