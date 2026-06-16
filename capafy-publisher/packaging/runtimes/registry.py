from __future__ import annotations

from functools import lru_cache

from packaging._shared.env_profiles import load_profile
from packaging._shared.runtimes.contracts import TargetDescriptor


DEFAULT_TARGET = "openclaw"


@lru_cache(maxsize=None)
def build_target_descriptors() -> dict[str, TargetDescriptor]:
    descriptors: dict[str, TargetDescriptor] = {}

    from packaging.runtimes.adapters import list_runtime_adapters

    for adapter in list_runtime_adapters():
        for descriptor in adapter.descriptors():
            descriptors[descriptor.target_id] = descriptor
    return descriptors


def list_target_descriptors() -> dict[str, TargetDescriptor]:
    return dict(build_target_descriptors())


def get_target_descriptor(name: str) -> TargetDescriptor:
    descriptors = build_target_descriptors()
    normalized = str(name or "").strip()
    if not normalized:
        raise ValueError("target name must not be empty")
    try:
        return descriptors[normalized]
    except KeyError as exc:
        raise ValueError(f"Unknown packaging target: {name}") from exc


@lru_cache(maxsize=None)
def get_profile_target_descriptor(env_id: str) -> tuple[dict, TargetDescriptor]:
    descriptor = get_target_descriptor(env_id)
    profile_env_id = str(descriptor.profile_env_id or descriptor.target_id).strip()
    profile = load_profile(profile_env_id)
    loaded_env_id = str(profile.get("env_id", "")).strip()
    if loaded_env_id != profile_env_id:
        raise ValueError(f"{profile_env_id} profile env_id={loaded_env_id} does not match its target descriptor")
    return profile, descriptor


__all__ = [
    "DEFAULT_TARGET",
    "build_target_descriptors",
    "get_profile_target_descriptor",
    "get_target_descriptor",
    "list_target_descriptors",
]
