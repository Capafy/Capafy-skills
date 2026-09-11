from __future__ import annotations
from typing import Mapping, Optional

import os
import sys
from pathlib import Path

from packaging.common.home import safe_expanduser_path


def _platform_default_hermes_home() -> Path:
    if sys.platform == "win32":
        local_appdata = str(os.environ.get("LOCALAPPDATA", "") or "").strip()
        return (Path(local_appdata) if local_appdata else Path.home() / "AppData" / "Local") / "hermes"
    return Path.home() / ".hermes"


DEFAULT_HERMES_HOME = _platform_default_hermes_home()


def resolve_hermes_home(*, env: Optional[Mapping[str, str]] = None) -> Path:
    runtime_env = env if env is not None else os.environ
    hermes_home_env = str(runtime_env.get("HERMES_HOME", "") or "").strip()
    if hermes_home_env:
        return safe_expanduser_path(hermes_home_env).resolve()
    return DEFAULT_HERMES_HOME.resolve()


__all__ = [
    "DEFAULT_HERMES_HOME",
    "resolve_hermes_home",
]
