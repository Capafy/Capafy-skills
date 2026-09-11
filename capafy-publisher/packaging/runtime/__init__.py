from __future__ import annotations

# Keep this package free of module-load imports from packaging.publish.
# Runtime hooks should lazy-load publish-profile modules inside functions.

from packaging.runtime.registry import (
    DEFAULT_TARGET,
    clear_target_cache,
    get_default_target,
    get_target_descriptor,
    get_target,
    list_target_descriptors,
)
from packaging.runtime.resolution import (
    OPENCLAW_MIN_VERSION,
    TargetResolution,
    build_runtime_metadata,
    detect_openclaw_target_resolution,
    resolve_target_name,
    resolve_target_request,
)


def validate_env_runtime(profile, runtime_root, *, env_id):
    """Lazily load publish-backed validation to keep runtime imports acyclic."""
    from packaging.runtime.validation import validate_env_runtime as _validate_env_runtime

    return _validate_env_runtime(profile, runtime_root, env_id=env_id)

__all__ = [
    "DEFAULT_TARGET",
    "OPENCLAW_MIN_VERSION",
    "TargetResolution",
    "build_runtime_metadata",
    "clear_target_cache",
    "detect_openclaw_target_resolution",
    "get_default_target",
    "get_target",
    "get_target_descriptor",
    "list_target_descriptors",
    "resolve_target_name",
    "resolve_target_request",
    "validate_env_runtime",
]
