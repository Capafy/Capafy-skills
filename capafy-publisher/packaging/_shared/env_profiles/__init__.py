from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path



ENV_PROFILES_DIR = Path(__file__).resolve().parent


_PROFILE_LIST_KEYS = (
    "skill_roots",
    "asset_roots",
    "fixed_scan_files",
    "fixed_stage_files",
    "redact_files",
)
_PROFILE_STRING_LIST_KEYS = (
    "discovery_skill_precedence",
)


def _profile_path(env_id: str) -> Path:
    return ENV_PROFILES_DIR / f"{env_id}.json"


def _require_dict(value: object, *, label: str, path: Path) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{path}: {label} must be an object")
    return value


def _require_list(value: object, *, label: str, path: Path) -> list:
    if not isinstance(value, list):
        raise ValueError(f"{path}: {label} must be a list")
    return value


def _validate_profile(profile: object, *, path: Path, expected_env_id: str | None = None) -> dict:
    if not isinstance(profile, dict):
        raise ValueError(f"invalid profile format: {path}")
    if expected_env_id is not None and profile.get("env_id") != expected_env_id:
        raise ValueError(f"profile env_id does not match: {path}")

    runtime_env = _require_dict(profile.get("runtime_env"), label="runtime_env", path=path)

    target_registration = profile.get("target_registration")
    if target_registration is not None:
        _require_dict(target_registration, label="target_registration", path=path)

    runtime_command = runtime_env.get("command")
    if runtime_command is not None:
        _require_list(runtime_command, label="runtime_env.command", path=path)

    for key in _PROFILE_LIST_KEYS:

        for index, item in enumerate(_require_list(profile.get(key, []), label=key, path=path)):
            item_dict = _require_dict(item, label=f"{key}[{index}]", path=path)
            base = str(item_dict.get("base", "home")).strip() or "home"
            if base in {"cwd", "workspace"}:
                raise ValueError(f"{path}: {key}[{index}].base cannot be {base}; use runtime_dir")
            if base not in {"absolute", "home", "runtime_dir"}:
                raise ValueError(f"{path}: {key}[{index}].base is unknown: {base}")

    for key in _PROFILE_STRING_LIST_KEYS:
        for index, item in enumerate(_require_list(profile.get(key, []), label=key, path=path)):
            if not isinstance(item, str):
                raise ValueError(f"{path}: {key}[{index}] must be a string")

    return profile


def _load_profile_from_path(path: Path, *, expected_env_id: str | None = None) -> dict:
    profile = json.loads(path.read_text(encoding="utf-8"))
    return _validate_profile(profile, path=path, expected_env_id=expected_env_id)


@lru_cache(maxsize=None)
def _load_profile_cached(env_id: str) -> dict:
    path = _profile_path(env_id)
    if not path.is_file():
        raise ValueError(f"unknown environment profile: {env_id}")
    return _load_profile_from_path(path, expected_env_id=env_id)


def load_profile(env_id: str) -> dict:
    return copy.deepcopy(_load_profile_cached(env_id))


def string_tuple_profile_value(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    values: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        normalized = item.strip()
        if normalized:
            values.append(normalized)
    return tuple(values)


@lru_cache(maxsize=1)
def _list_profiles_cached() -> tuple[dict, ...]:
    profiles: list[dict] = []
    for path in sorted(ENV_PROFILES_DIR.glob("*.json")):
        profiles.append(_load_profile_from_path(path))
    return tuple(profiles)


def list_profiles() -> list[dict]:
    return copy.deepcopy(list(_list_profiles_cached()))





load_profile.cache_clear = _load_profile_cached.cache_clear  # type: ignore[attr-defined]
load_profile.cache_info = _load_profile_cached.cache_info  # type: ignore[attr-defined]


list_profiles.cache_clear = _list_profiles_cached.cache_clear  # type: ignore[attr-defined]
list_profiles.cache_info = _list_profiles_cached.cache_info  # type: ignore[attr-defined]


__all__ = [
    "ENV_PROFILES_DIR",
    "list_profiles",
    "load_profile",
    "string_tuple_profile_value",
]
