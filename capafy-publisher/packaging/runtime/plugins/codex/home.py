from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Mapping, Optional

from packaging.common.fs import windows_drive_mount_candidates, windows_path_parts
from packaging.common.home import current_home_from_env, safe_expanduser_path


_WINDOWS_DRIVE_PATH_PATTERN = re.compile(r"^(?P<drive>[A-Za-z]):[\\/](?P<rest>.*)$")


def _custom_codex_home(raw_value: str, *, env: Mapping[str, str]) -> Path:
    match = _WINDOWS_DRIVE_PATH_PATTERN.match(raw_value)
    if match and os.name != "nt":
        parts = windows_path_parts(match.group("rest"))
        if not parts:
            raise ValueError("CODEX_HOME must not be a filesystem root")
        candidates = [
            root.joinpath(*parts)
            for root in windows_drive_mount_candidates(match.group("drive"))
        ]
        candidate = next((path for path in candidates if path.exists()), candidates[0])
    else:
        candidate = safe_expanduser_path(raw_value, environ=env)
    if not candidate.is_absolute():
        raise ValueError("CODEX_HOME must be an absolute path")
    resolved = candidate.resolve(strict=False)
    if resolved == Path(resolved.anchor):
        raise ValueError("CODEX_HOME must not be a filesystem root")
    return resolved


def resolve_codex_home(
    *,
    env: Optional[Mapping[str, str]] = None,
    home: Optional[Path] = None,
) -> Path:
    runtime_env = os.environ if env is None else env
    raw_value = str(runtime_env.get("CODEX_HOME", "") or "").strip()
    if raw_value:
        return _custom_codex_home(raw_value, env=runtime_env)

    resolved_home = home or current_home_from_env(runtime_env)
    if resolved_home is None:
        raise ValueError("CODEX_HOME fallback requires a resolvable home directory")
    return safe_expanduser_path(resolved_home, environ=runtime_env).resolve(strict=False) / ".codex"


__all__ = ["resolve_codex_home"]
