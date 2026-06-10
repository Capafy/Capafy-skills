from __future__ import annotations
from typing import Optional

from collections.abc import Iterator, Mapping
from functools import lru_cache

from packaging._shared.env_profiles import load_profile
from packaging._shared.runtimes.contracts import PackagingTarget, TargetDescriptor
from packaging.runtimes.registry import (
    DEFAULT_TARGET,
    get_profile_target_descriptor,
    get_target_descriptor,
    list_target_descriptors,
)
from packaging.runtimes.resolution import (
    resolve_runtime_validation_target,
    resolve_target_name,
)


@lru_cache(maxsize=None)
def get_profile_target(env_id: str) -> tuple[dict, PackagingTarget]:
    profile, _ = get_profile_target_descriptor(env_id)
    try:
        from packaging.runtimes.plugins import get_runtime_plugin_for_target

        plugin = get_runtime_plugin_for_target(env_id)
    except ValueError:
        plugin = None
    if plugin is not None and plugin.target_factory is not None:
        descriptor = get_target_descriptor(env_id)
        return profile, plugin.target_factory(descriptor, profile)
    raise ValueError(f"{env_id} does not have a concrete profile target class")


def _is_dispatch_target_descriptor(descriptor: TargetDescriptor) -> bool:
    return descriptor.profile_env_id is not None or descriptor.runtime_generation is not None


def build_target_instances() -> dict[str, PackagingTarget]:
    targets: dict[str, PackagingTarget] = {}
    for descriptor in list_target_descriptors().values():
        if not _is_dispatch_target_descriptor(descriptor):
            continue
        from packaging.runtimes.plugins import get_runtime_plugin_for_target

        try:
            plugin = get_runtime_plugin_for_target(descriptor.target_id)
        except ValueError as exc:
            raise ValueError(f"{descriptor.target_id} does not have a registered target builder") from exc
        if plugin.target_factory is None:
            raise ValueError(f"{descriptor.target_id} does not have a registered target builder")
        targets[descriptor.target_id] = plugin.target_factory(
            descriptor,
            load_profile(descriptor.profile_env_id) if descriptor.profile_env_id else {},
        )
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


def get_runtime_validation_target(name: Optional[str]) -> tuple[PackagingTarget, str]:
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
