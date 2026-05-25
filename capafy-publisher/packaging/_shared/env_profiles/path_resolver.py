from __future__ import annotations
from typing import Optional

import os
from pathlib import Path

from packaging._shared.common.home import current_home_from_env, safe_expanduser_path


def _resolve_base_root(
    spec: dict,
    *,
    home: Optional[Path] = None,
    runtime_dir: Optional[str] = None,
) -> Path:
    base = str(spec.get("base", "home")).strip() or "home"
    if base == "home":
        resolved_home = safe_expanduser_path(home) if home is not None else current_home_from_env()
        if resolved_home is None:
            raise ValueError("base=home requires a resolvable home directory")
        return resolved_home
    if base == "runtime_dir":
        if runtime_dir is None:
            raise ValueError("base=runtime_dir requires a runtime_dir value")
        return safe_expanduser_path(runtime_dir).resolve()
    if base == "absolute":
        root_path = str(spec.get("root_path", "")).strip()
        if not root_path:
            raise ValueError("absolute path spec is missing root_path")
        return safe_expanduser_path(root_path)
    raise ValueError(f"unknown path base: {base}")


def _resolve_root_override(override: dict) -> Optional[Path]:
    env_name = str(override.get("env", "")).strip()
    if not env_name:
        return None
    raw = os.environ.get(env_name)
    if not raw:
        return None
    candidate = safe_expanduser_path(raw)
    suffix = str(override.get("suffix", "")).strip().strip("/")
    if suffix:
        candidate = candidate / suffix
    return candidate


def resolve_path_spec(
    spec: dict,
    *,
    home: Optional[Path] = None,
    runtime_dir: Optional[str] = None,
) -> Path:
    path_env = str(spec.get("path_env", "")).strip()
    if path_env:
        raw = os.environ.get(path_env)
        if raw:
            return safe_expanduser_path(raw)

    for override in spec.get("root_overrides", []):
        if not isinstance(override, dict):
            continue
        override_root = _resolve_root_override(override)
        if override_root is None:
            continue
        relative = str(spec.get("path", "."))
        if relative in {"", "."}:
            return override_root
        return safe_expanduser_path(override_root / relative)

    root = _resolve_base_root(spec, home=home, runtime_dir=runtime_dir)
    root_path = str(spec.get("root_path", "")).strip()
    if root_path and root_path != ".":
        root = safe_expanduser_path(root / root_path)

    relative = str(spec.get("path", "."))
    if relative in {"", "."}:
        return root
    return safe_expanduser_path(root / relative)


__all__ = ["resolve_path_spec"]
