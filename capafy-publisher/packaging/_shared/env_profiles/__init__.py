from __future__ import annotations
from typing import Optional

import copy
import json
from functools import lru_cache
from pathlib import Path



ENV_PROFILES_DIR = Path(__file__).resolve().parent


_PROFILE_LIST_KEYS = (
    "skill_roots",
    "fixed_scan_files",
)
_PROFILE_STRING_LIST_KEYS = (
    "discovery_skill_precedence",
    "url_proxy_os_fallback_names",
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


def _validate_platform_contract(profile: dict, *, path: Path) -> None:
    platform_contract = profile.get("platform_contract")
    if platform_contract is None:
        return
    contract = _require_dict(platform_contract, label="platform_contract", path=path)
    for index, item in enumerate(_require_list(contract.get("config_files", []), label="platform_contract.config_files", path=path)):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{path}: platform_contract.config_files[{index}] must be a non-empty string")
    for index, item in enumerate(_require_list(contract.get("optional_config_files", []), label="platform_contract.optional_config_files", path=path)):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{path}: platform_contract.optional_config_files[{index}] must be a non-empty string")

    env_vars = _require_dict(contract.get("env_vars", {}), label="platform_contract.env_vars", path=path)
    for env_name, raw_spec in env_vars.items():
        if not isinstance(env_name, str) or not env_name.strip():
            raise ValueError(f"{path}: platform_contract.env_vars keys must be non-empty strings")
        spec = _require_dict(raw_spec, label=f"platform_contract.env_vars[{env_name}]", path=path)
        for field in ("service", "canonical_url"):
            value = spec.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{path}: platform_contract.env_vars[{env_name}].{field} must be a non-empty string")


def _validate_profile(profile: object, *, path: Path, expected_env_id: Optional[str] = None) -> dict:
    if not isinstance(profile, dict):
        raise ValueError(f"invalid profile format: {path}")
    if expected_env_id is not None:
        raw_env_id = str(profile.get("env_id", "") or "").strip()
        if raw_env_id and raw_env_id != expected_env_id:
            raise ValueError(f"profile env_id does not match: {path}")
        profile.setdefault("env_id", expected_env_id)

    runtime_env = _require_dict(profile.get("runtime_env"), label="runtime_env", path=path)

    _validate_platform_contract(profile, path=path)

    runtime_command = runtime_env.get("command")
    if runtime_command is not None:
        _require_list(runtime_command, label="runtime_env.command", path=path)

    for key in _PROFILE_LIST_KEYS:
        profile.setdefault(key, [])

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


def _load_profile_from_path(path: Path, *, expected_env_id: Optional[str] = None) -> dict:
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
        profiles.append(_load_profile_from_path(path, expected_env_id=path.stem))
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
