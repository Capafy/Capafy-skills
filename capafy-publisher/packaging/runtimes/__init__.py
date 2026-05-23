from __future__ import annotations

from packaging.runtimes.factory import (
    TARGETS,
    build_target_instances,
    get_default_target,
    get_profile_target,
    get_runtime_validation_target,
    get_target,
)
from packaging.runtimes.registry import (
    DEFAULT_TARGET,
    build_target_descriptors,
    get_target_descriptor,
    list_target_descriptors,
)
from packaging.runtimes.resolution import (
    OPENCLAW_LEGACY_TARGET,
    OPENCLAW_MODERN_MIN_VERSION,
    OPENCLAW_MODERN_TARGET,
    TargetResolutionRule,
    TargetResolution,
    build_runtime_metadata,
    detect_openclaw_target_resolution,
    get_target_resolution_rule,
    resolve_runtime_validation_target,
    resolve_target_name,
    resolve_target_request,
)

__all__ = [
    "DEFAULT_TARGET",
    "OPENCLAW_LEGACY_TARGET",
    "OPENCLAW_MODERN_MIN_VERSION",
    "OPENCLAW_MODERN_TARGET",
    "TARGETS",
    "TargetResolutionRule",
    "TargetResolution",
    "build_runtime_metadata",
    "build_target_descriptors",
    "build_target_instances",
    "detect_openclaw_target_resolution",
    "get_default_target",
    "get_profile_target",
    "get_runtime_validation_target",
    "get_target",
    "get_target_resolution_rule",
    "get_target_descriptor",
    "list_target_descriptors",
    "resolve_runtime_validation_target",
    "resolve_target_name",
    "resolve_target_request",
]
