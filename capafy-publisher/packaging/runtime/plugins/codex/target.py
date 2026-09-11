from __future__ import annotations

from pathlib import Path

from packaging.runtime.plugins.codex.home import resolve_codex_home
from packaging.runtime.stage_plan import HomeBackedProfileTarget


class CodexTarget(HomeBackedProfileTarget):
    _DEFAULT_ENV_ID = "codex"
    _HOME_PREFIX = ".codex"
    _STAGE_PLAN_PREFIXES = (".codex",)

    def _resolve_runtime_home(self) -> Path:
        return resolve_codex_home()


__all__ = ["CodexTarget"]
