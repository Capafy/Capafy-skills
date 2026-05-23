from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Mapping, Optional, Union


PathLike = Union[str, Path]


def _normalize_key(path: Path) -> str:
    return str(path).replace("\\", "/").rstrip("/").casefold()


def _env_home_values(environ: Mapping[str, str]) -> list[str]:
    values: list[str] = []
    for key in ("HOME", "USERPROFILE"):
        value = str(environ.get(key) or "").strip()
        if value:
            values.append(value)
    drive = str(environ.get("HOMEDRIVE") or "").strip()
    path = str(environ.get("HOMEPATH") or "").strip()
    if drive and path:
        values.append(f"{drive}{path}")
    return values


def _system_home_fallback() -> Optional[Path]:
    try:
        import pwd

        value = str(pwd.getpwuid(os.getuid()).pw_dir or "").strip()
    except (AttributeError, ImportError, KeyError, OSError):
        value = ""
    if not value or value.startswith("~"):
        return None
    return Path(value)


def home_roots_from_env(
    environ: Optional[Mapping[str, str]] = None,
    *,
    include_system_fallback: bool = True,
) -> list[Path]:
    env = os.environ if environ is None else environ
    raw_values = _env_home_values(env)
    if include_system_fallback and not raw_values:
        fallback = _system_home_fallback()
        if fallback is not None:
            raw_values.append(str(fallback))

    roots: list[Path] = []
    seen: set[str] = set()
    for raw in raw_values:
        if raw.startswith("~"):
            continue
        root = Path(raw)
        key = _normalize_key(root)
        if key and key not in seen:
            roots.append(root)
            seen.add(key)
    return roots


def current_home_from_env(
    environ: Optional[Mapping[str, str]] = None,
    *,
    include_system_fallback: bool = True,
) -> Optional[Path]:
    roots = home_roots_from_env(environ, include_system_fallback=include_system_fallback)
    return roots[0] if roots else None


def _join_home_text(home: Path, rest: str) -> Path:
    parts = [part for part in re.split(r"[\\/]+", rest.strip("\\/")) if part]
    if not parts:
        return home
    return home.joinpath(*parts)


def safe_expanduser_path(
    path: PathLike,
    *,
    environ: Optional[Mapping[str, str]] = None,
    home: Optional[Path] = None,
    include_system_fallback: bool = True,
) -> Path:
    text = str(path)
    if text == "~" or text.startswith("~/") or text.startswith("~\\"):
        resolved_home = home or current_home_from_env(
            environ,
            include_system_fallback=include_system_fallback,
        )
        if resolved_home is None:
            return Path(text)
        if text == "~":
            return resolved_home
        return _join_home_text(resolved_home, text[2:])
    return Path(text)


__all__ = [
    "current_home_from_env",
    "home_roots_from_env",
    "safe_expanduser_path",
]
