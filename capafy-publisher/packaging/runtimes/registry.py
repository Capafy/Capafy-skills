from __future__ import annotations
from typing import Optional

from functools import lru_cache

from packaging._shared.env_profiles import list_profiles, load_profile
from packaging._shared.runtimes.contracts import TargetDescriptor
from packaging.runtimes.resolution import OPENCLAW_LEGACY_TARGET, OPENCLAW_MODERN_TARGET


DEFAULT_TARGET = "openclaw"
_ENV_TARGET_IDS = frozenset({"codex", "claude_code"})


def _build_profile_target_descriptor(profile: dict) -> Optional[TargetDescriptor]:
    env_id = str(profile.get("env_id", "")).strip()
    if not env_id or env_id not in _ENV_TARGET_IDS:
        return None

    target_registration = profile.get("target_registration", {})
    if not isinstance(target_registration, dict):
        target_registration = {}
    return TargetDescriptor(
        target_id=env_id,
        canonical_name=env_id,
        profile_env_id=env_id,
        runtime_generation=str(target_registration.get("runtime_generation", "")).strip() or None,
    )


@lru_cache(maxsize=None)
def build_target_descriptors() -> dict[str, TargetDescriptor]:
    descriptors: dict[str, TargetDescriptor] = {
        DEFAULT_TARGET: TargetDescriptor(
            target_id=DEFAULT_TARGET,
            canonical_name="openclaw",
        ),
        OPENCLAW_LEGACY_TARGET: TargetDescriptor(
            target_id=OPENCLAW_LEGACY_TARGET,
            canonical_name="openclaw",
            runtime_generation=OPENCLAW_LEGACY_TARGET,
            runtime_variant="legacy",
            feature_tags=("legacy",),
        ),
        OPENCLAW_MODERN_TARGET: TargetDescriptor(
            target_id=OPENCLAW_MODERN_TARGET,
            canonical_name="openclaw",
            runtime_generation=OPENCLAW_MODERN_TARGET,
            runtime_variant="modern",
            feature_tags=("bundle_aware",),
        ),
    }

    for profile in list_profiles():
        descriptor = _build_profile_target_descriptor(profile)
        if descriptor is None:
            continue
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
