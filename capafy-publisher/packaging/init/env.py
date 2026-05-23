from __future__ import annotations

from pathlib import Path

from packaging._shared.env_profiles import load_profile
from packaging.runtimes import build_runtime_metadata, get_target


def prepare_environment(
    env_name: str,
    *,
    runtime_dir: str,
) -> dict:
    normalized_env_name = str(env_name or "").strip()
    if not normalized_env_name:
        raise ValueError("env_name is required")

    normalized_runtime_dir = str(runtime_dir or "").strip()
    if not normalized_runtime_dir:
        raise ValueError("runtime_dir is required")
    normalized_runtime_dir = str(Path(normalized_runtime_dir).expanduser())

    target = get_target(normalized_env_name)
    profile_env_name = str(target.profile_env_id() or normalized_env_name).strip()
    if not profile_env_name:
        raise ValueError(f"{normalized_env_name} does not declare a profile environment id")

    profile = load_profile(profile_env_name)
    normalized_runtime_dir = target.prepare_runtime_dir(normalized_runtime_dir)

    payload = {
        "env_id": normalized_env_name,
        "display_name": str(profile.get("display_name", normalized_env_name)),
        "runtime_dir": normalized_runtime_dir,
    }
    payload.update(build_runtime_metadata(normalized_env_name))
    return payload


__all__ = [
    "prepare_environment",
]
