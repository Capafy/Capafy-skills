from __future__ import annotations
from typing import Mapping, Optional

import os
from pathlib import Path

from packaging._shared.common.home import safe_expanduser_path


DEFAULT_HERMES_HOME = Path.home() / ".hermes"
ACTIVE_PROFILE_FILE = "active_profile"


def _profile_dir(profile: str) -> Path:
    normalized = str(profile or "").strip()
    if not normalized:
        return DEFAULT_HERMES_HOME.resolve()
    candidate = safe_expanduser_path(normalized)
    if candidate.is_absolute():
        return candidate.resolve()
    return (DEFAULT_HERMES_HOME / "profiles" / normalized).resolve()


def _read_active_profile_marker(base_home: Path) -> str:
    marker = base_home / ACTIVE_PROFILE_FILE
    try:
        return marker.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def resolve_hermes_home(*, env: Optional[Mapping[str, str]] = None) -> Path:
    runtime_env = env if env is not None else os.environ
    hermes_home_env = str(runtime_env.get("HERMES_HOME", "") or "").strip()
    if hermes_home_env:
        return safe_expanduser_path(hermes_home_env).resolve()
    default_home = DEFAULT_HERMES_HOME.resolve()
    active = _read_active_profile_marker(default_home)
    if active:
        return _profile_dir(active)
    return default_home


def list_hermes_profiles() -> list[str]:
    profiles_root = DEFAULT_HERMES_HOME / "profiles"
    try:
        return sorted(path.name for path in profiles_root.iterdir() if path.is_dir())
    except OSError:
        return []


__all__ = [
    "ACTIVE_PROFILE_FILE",
    "DEFAULT_HERMES_HOME",
    "list_hermes_profiles",
    "resolve_hermes_home",
]
