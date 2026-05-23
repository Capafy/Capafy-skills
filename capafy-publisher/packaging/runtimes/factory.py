from __future__ import annotations

from collections.abc import Iterator, Mapping
from functools import lru_cache

from packaging._shared.runtimes.contracts import PackagingTarget, TargetDescriptor
from packaging.runtimes.registry import DEFAULT_TARGET, get_profile_target_descriptor, list_target_descriptors
from packaging.runtimes.resolution import (
    OPENCLAW_LEGACY_TARGET,
    OPENCLAW_MODERN_TARGET,
    resolve_runtime_validation_target,
    resolve_target_name,
)


@lru_cache(maxsize=None)
def get_profile_target(env_id: str) -> tuple[dict, PackagingTarget]:
    profile, _ = get_profile_target_descriptor(env_id)
    if env_id == "codex":
        from packaging.configure.runtimes.codex.target import CodexTarget

        return profile, CodexTarget(profile)
    if env_id == "claude_code":
        from packaging.configure.runtimes.claude_code.target import ClaudeCodeTarget

        return profile, ClaudeCodeTarget(profile)
    raise ValueError(f"{env_id} does not have a concrete profile target class")


def _build_profile_target_instance(descriptor: TargetDescriptor) -> PackagingTarget:
    if not descriptor.profile_env_id:
        raise ValueError(f"{descriptor.target_id} is missing profile_env_id, so {descriptor.target_id} target cannot be built")
    _, target = get_profile_target(descriptor.profile_env_id)
    return target


def _build_openclaw_instance(descriptor: TargetDescriptor) -> PackagingTarget:
    from packaging.configure.runtimes.openclaw import target as openclaw_target

    if descriptor.runtime_variant == "legacy":
        return openclaw_target.LEGACY_TARGET
    if descriptor.runtime_variant == "modern":
        return openclaw_target.MODERN_TARGET
    raise ValueError(f"{descriptor.target_id} is missing openclaw runtime_variant, so the target cannot be built")


_TARGET_BUILDERS = {
    "codex": _build_profile_target_instance,
    "claude_code": _build_profile_target_instance,
    OPENCLAW_LEGACY_TARGET: _build_openclaw_instance,
    OPENCLAW_MODERN_TARGET: _build_openclaw_instance,
}


def _is_dispatch_target_descriptor(descriptor: TargetDescriptor) -> bool:
    return descriptor.profile_env_id is not None or descriptor.runtime_generation is not None


def build_target_instances() -> dict[str, PackagingTarget]:
    targets: dict[str, PackagingTarget] = {}
    for descriptor in list_target_descriptors().values():
        if not _is_dispatch_target_descriptor(descriptor):
            continue
        try:
            builder = _TARGET_BUILDERS[descriptor.target_id]
        except KeyError as exc:
            raise ValueError(f"{descriptor.target_id} does not have a registered target builder") from exc
        targets[descriptor.target_id] = builder(descriptor)
    return targets


class _LazyTargetRegistry(Mapping):
    @staticmethod
    @lru_cache(maxsize=1)
    def _targets() -> dict[str, PackagingTarget]:
        return build_target_instances()

    def __getitem__(self, key: str) -> PackagingTarget:
        return self._targets()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._targets())

    def __len__(self) -> int:
        return len(self._targets())

    def __repr__(self) -> str:
        return repr(self._targets())


TARGETS: Mapping[str, PackagingTarget] = _LazyTargetRegistry()


def get_target(name: str) -> PackagingTarget:
    resolved_name = resolve_target_name(name)
    try:
        return TARGETS[resolved_name]
    except KeyError as exc:
        raise ValueError(f"unknown packaging target: {name}") from exc


def get_default_target() -> PackagingTarget:
    return get_target(DEFAULT_TARGET)


def get_runtime_validation_target(name: str | None) -> tuple[PackagingTarget, str]:
    dispatch_name, reported_name = resolve_runtime_validation_target(name)
    try:
        return TARGETS[dispatch_name], reported_name
    except KeyError as exc:
        raise ValueError(f"unknown packaging target: {name}") from exc


__all__ = [
    "TARGETS",
    "build_target_instances",
    "get_default_target",
    "get_profile_target",
    "get_runtime_validation_target",
    "get_target",
]
