from __future__ import annotations

from pathlib import Path

from packaging.configure.runtimes.env_profile_target import EnvProfileTarget
from packaging.configure.runtimes.codex import scan_hints as codex_scan_hints
from packaging.configure.scan.env_scan_rules import logical_env_source_path


class CodexTarget(EnvProfileTarget):
    _DEFAULT_ENV_ID = "codex"

    def collect_special_scan_candidates(
        self,
        path: Path,
        text: str,
        annotate_candidate,
    ) -> tuple[dict[str, str], dict[str, str], dict[str, str], list[dict]]:
        if path.name != "config.toml":
            return {}, {}, {}, []
        display_path = path.name
        source_display_path = logical_env_source_path(path, display_path)
        env_hints, val_hints, candidates = codex_scan_hints.collect_codex_toml_config_hints(
            text,
            display_path,
            source_display_path,
            annotate_candidate,
        )
        return env_hints, {}, val_hints, candidates

    def should_scan_structured_values(self, relpath: str) -> bool:
        return codex_scan_hints.should_scan_codex_structured_values(relpath)


__all__ = [
    "CodexTarget",
]
