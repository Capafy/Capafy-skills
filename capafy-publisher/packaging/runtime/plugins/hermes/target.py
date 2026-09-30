from __future__ import annotations

from pathlib import Path

from packaging.runtime.plugins.hermes.config import resolve_hermes_home
from packaging.runtime.stage_plan import HomeBackedProfileTarget


class HermesTarget(HomeBackedProfileTarget):
    _DEFAULT_ENV_ID = "hermes"
    _HOME_PREFIX = ".hermes"

    def _resolve_runtime_home(self) -> Path:
        return resolve_hermes_home()


__all__ = [
    "HermesTarget",
]
