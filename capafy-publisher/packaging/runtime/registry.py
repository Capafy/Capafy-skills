from __future__ import annotations

from functools import lru_cache
from importlib import import_module

from packaging.runtime.contracts import PackagingTarget, RuntimeAdapter, TargetDescriptor
from packaging.runtime.profiles import load_profile


DEFAULT_TARGET = "openclaw"
_CODEX_RUNTIME_GENERATION = "codex_standalone"
_HERMES_RUNTIME_GENERATION = "hermes_v1"


def _codex_target_factory(profile: dict):
    CodexTarget = import_module("packaging.runtime.plugins.codex.target").CodexTarget
    return CodexTarget(profile)


def _claude_code_target_factory(profile: dict):
    EnvProfileTarget = import_module("packaging.runtime.stage_plan").EnvProfileTarget
    return EnvProfileTarget(profile)


def _hermes_target_factory(profile: dict):
    HermesTarget = import_module("packaging.runtime.plugins.hermes.target").HermesTarget
    return HermesTarget(profile)


def _openclaw_target_factory(profile: dict):
    OpenClawTarget = import_module("packaging.runtime.plugins.openclaw.target").OpenClawTarget
    return OpenClawTarget(profile)


def _codex_provider_runtime_factory():
    CodexRuntime = import_module("packaging.runtime.plugins.codex.url_proxy").CodexRuntime
    return CodexRuntime()


def _claude_code_provider_runtime_factory():
    ClaudeCodeRuntime = import_module(
        "packaging.runtime.plugins.claude_code.url_proxy"
    ).ClaudeCodeRuntime
    return ClaudeCodeRuntime()


def _hermes_provider_runtime_factory():
    HermesRuntime = import_module("packaging.runtime.plugins.hermes.url_proxy").HermesRuntime
    return HermesRuntime()


def _openclaw_provider_runtime_factory():
    OpenClawRuntime = import_module(
        "packaging.runtime.plugins.openclaw.url_proxy"
    ).OpenClawRuntime
    return OpenClawRuntime()


_RUNTIME_ADAPTERS = (
    RuntimeAdapter(
        runtime_id="codex",
        descriptors=(
            TargetDescriptor(
                target_id="codex",
                profile_env_id="codex",
                runtime_generation=_CODEX_RUNTIME_GENERATION,
            ),
        ),
        target_factory=_codex_target_factory,
        provider_runtime_factory=_codex_provider_runtime_factory,
    ),
    RuntimeAdapter(
        runtime_id="claude_code",
        descriptors=(
            TargetDescriptor(
                target_id="claude_code",
                profile_env_id="claude_code",
            ),
        ),
        target_factory=_claude_code_target_factory,
        provider_runtime_factory=_claude_code_provider_runtime_factory,
    ),
    RuntimeAdapter(
        runtime_id="openclaw",
        descriptors=(
            TargetDescriptor(
                target_id="openclaw",
                profile_env_id="openclaw",
            ),
        ),
        target_factory=_openclaw_target_factory,
        provider_runtime_factory=_openclaw_provider_runtime_factory,
    ),
    RuntimeAdapter(
        runtime_id="hermes",
        descriptors=(
            TargetDescriptor(
                target_id="hermes",
                profile_env_id="hermes",
                runtime_generation=_HERMES_RUNTIME_GENERATION,
            ),
        ),
        target_factory=_hermes_target_factory,
        provider_runtime_factory=_hermes_provider_runtime_factory,
    ),
)


def list_target_descriptors() -> dict[str, TargetDescriptor]:
    descriptors: dict[str, TargetDescriptor] = {}
    for adapter in _RUNTIME_ADAPTERS:
        for descriptor in adapter.descriptors:
            descriptors[descriptor.target_id] = descriptor
    return descriptors


def get_target_descriptor(name: str) -> TargetDescriptor:
    descriptors = list_target_descriptors()
    normalized = str(name or "").strip()
    if not normalized:
        raise ValueError("target name must not be empty")
    try:
        return descriptors[normalized]
    except KeyError as exc:
        raise ValueError(f"Unknown packaging target: {name}") from exc


def get_runtime_adapter(runtime_id: str) -> RuntimeAdapter:
    normalized = str(runtime_id or "").strip()
    for adapter in _RUNTIME_ADAPTERS:
        if adapter.runtime_id == normalized:
            return adapter
    raise ValueError(f"unknown runtime adapter: {runtime_id}")


def get_runtime_adapter_for_target(target_id: str) -> RuntimeAdapter:
    normalized = str(target_id or "").strip()
    for adapter in _RUNTIME_ADAPTERS:
        if any(descriptor.target_id == normalized for descriptor in adapter.descriptors):
            return adapter
    raise ValueError(f"unknown runtime adapter target: {target_id}")


def build_provider_runtime_for_target(target_id: str):
    """Build the provider scanner registered for one packaging target."""
    adapter = get_runtime_adapter_for_target(target_id)
    runtime = adapter.provider_runtime_factory()
    required_methods = ("routes", "os_fallback_environment_names")
    if not all(callable(getattr(runtime, method_name, None)) for method_name in required_methods):
        raise TypeError(f"invalid provider runtime for target: {target_id}")
    return runtime


@lru_cache(maxsize=None)
def _target_instance(descriptor: TargetDescriptor) -> PackagingTarget:
    adapter = get_runtime_adapter_for_target(descriptor.target_id)
    return adapter.target_factory(
        load_profile(descriptor.profile_env_id) if descriptor.profile_env_id else {},
    )


def get_target(name: str) -> PackagingTarget:
    return _target_instance(get_target_descriptor(name))


def get_default_target() -> PackagingTarget:
    return get_target(DEFAULT_TARGET)


def clear_target_cache() -> None:
    _target_instance.cache_clear()


__all__ = [
    "DEFAULT_TARGET",
    "build_provider_runtime_for_target",
    "clear_target_cache",
    "get_default_target",
    "get_runtime_adapter",
    "get_runtime_adapter_for_target",
    "get_target",
    "get_target_descriptor",
    "list_target_descriptors",
]
