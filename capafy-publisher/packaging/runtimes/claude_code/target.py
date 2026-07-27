from __future__ import annotations

from pathlib import Path
from typing import Optional

from packaging.runtimes.profile_target import EnvProfileTarget


class ClaudeCodeTarget(EnvProfileTarget):
    _DEFAULT_ENV_ID = "claude_code"

    def selectable_unit_name(self, unit_path: Path, unit_type: str) -> Optional[str]:
        if unit_type != "skill":
            return None
        return unit_path.name


__all__ = ["ClaudeCodeTarget"]
