from __future__ import annotations

import re
from functools import lru_cache

from packaging._shared.env_profiles import list_profiles, load_profile
from packaging._shared.runtimes.contracts import TargetDescriptor
from packaging.runtimes.resolution import OPENCLAW_LEGACY_TARGET, OPENCLAW_MODERN_TARGET


DEFAULT_TARGET = "openclaw"
_ENV_TARGET_IDS = frozenset({"codex", "claude_code"})
_TARGET_SEPARATOR_PATTERN = re.compile(r"[-_\s]+")


def _target_lookup_variants(name: str) -> tuple[str, ...]:
    normalized = str(name or "").strip()
    if not normalized:
        return ()
    underscored = _TARGET_SEPARATOR_PATTERN.sub("_", normalized).strip("_")
    compact = _TARGET_SEPARATOR_PATTERN.sub("", normalized)
    variants: list[str] = []
    for value in (
        normalized,
        normalized.lower(),
        underscored,
        underscored.lower(),
        compact,
        compact.lower(),
    ):
        if value and value not in variants:
            variants.append(value)
    return tuple(variants)


def _descriptor_lookup_names(descriptor: TargetDescriptor) -> tuple[str, ...]:
    names = (
        descriptor.target_id,
        descriptor.profile_env_id or "",
        descriptor.runtime_generation or "",
    )
    variants: list[str] = []
    for name in names:
        for variant in _target_lookup_variants(name):
            if variant and variant not in variants:
                variants.append(variant)
    return tuple(variants)


def _resolve_descriptor_key(name: str, descriptors: dict[str, TargetDescriptor]) -> str:
    normalized = str(name or "").strip()
    if not normalized:
        raise ValueError("target name must not be empty")
    if normalized in descriptors:
        return normalized

    requested_variants = _target_lookup_variants(normalized)
    matches = [
        target_id
        for target_id, descriptor in descriptors.items()
        if any(variant in _descriptor_lookup_names(descriptor) for variant in requested_variants)
    ]
    unique_matches = sorted(set(matches))
    if len(unique_matches) == 1:
        return unique_matches[0]
    if len(unique_matches) > 1:
        raise ValueError(f"Ambiguous packaging target: {name}")
    raise ValueError(f"Unknown packaging target: {name}")


def _build_profile_target_descriptor(profile: dict) -> TargetDescriptor | None:
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
            aliases=(OPENCLAW_LEGACY_TARGET, OPENCLAW_MODERN_TARGET),
        ),
        OPENCLAW_LEGACY_TARGET: TargetDescriptor(
            target_id=OPENCLAW_LEGACY_TARGET,
            canonical_name="openclaw",
            runtime_generation=OPENCLAW_LEGACY_TARGET,
            runtime_variant="legacy",
            aliases=(DEFAULT_TARGET,),
            feature_tags=("legacy",),
        ),
        OPENCLAW_MODERN_TARGET: TargetDescriptor(
            target_id=OPENCLAW_MODERN_TARGET,
            canonical_name="openclaw",
            runtime_generation=OPENCLAW_MODERN_TARGET,
            runtime_variant="modern",
            aliases=(DEFAULT_TARGET,),
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
    resolved_key = _resolve_descriptor_key(name, descriptors)
    return descriptors[resolved_key]


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
