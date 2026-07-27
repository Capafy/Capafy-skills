from __future__ import annotations

from functools import lru_cache
from importlib import import_module

from packaging._shared.runtimes.contracts import RuntimeAdapter, TargetDescriptor


_CODEX_RUNTIME_GENERATION = "codex_standalone"
_HERMES_RUNTIME_GENERATION = "hermes_v1"


def _codex_target_factory(descriptor: TargetDescriptor, profile: dict):
    CodexTarget = import_module("packaging.runtimes.codex.target").CodexTarget
    return CodexTarget(profile)


def _claude_code_target_factory(descriptor: TargetDescriptor, profile: dict):
    ClaudeCodeTarget = import_module("packaging.runtimes.claude_code.target").ClaudeCodeTarget
    return ClaudeCodeTarget(profile)


def _hermes_target_factory(descriptor: TargetDescriptor, profile: dict):
    HermesTarget = import_module("packaging.runtimes.hermes.target").HermesTarget
    return HermesTarget(profile)


def _openclaw_target_factory(descriptor: TargetDescriptor, profile: dict):
    openclaw_target = import_module("packaging.runtimes.openclaw.target")
    return openclaw_target.TARGET


def _codex_url_proxy_runtime_factory():
    CodexRuntime = import_module("packaging.configure.runtimes.codex.url_proxy").CodexRuntime
    return CodexRuntime()


def _claude_code_url_proxy_runtime_factory():
    ClaudeCodeRuntime = import_module("packaging.configure.runtimes.claude_code.url_proxy").ClaudeCodeRuntime
    return ClaudeCodeRuntime()


def _hermes_url_proxy_runtime_factory():
    HermesRuntime = import_module("packaging.configure.runtimes.hermes.url_proxy").HermesRuntime
    return HermesRuntime()


def _openclaw_url_proxy_runtime_factory():
    OpenClawRuntime = import_module(
        "packaging.configure.runtimes.openclaw.url_proxy"
    ).OpenClawRuntime
    return OpenClawRuntime()


_RUNTIME_ADAPTERS = (
    RuntimeAdapter(
        runtime_id="codex",
        descriptors=(
            TargetDescriptor(
                target_id="codex",
                canonical_name="codex",
                profile_env_id="codex",
                runtime_generation=_CODEX_RUNTIME_GENERATION,
            ),
        ),
        target_factory=_codex_target_factory,
        url_proxy_runtime_factory=_codex_url_proxy_runtime_factory,
    ),
    RuntimeAdapter(
        runtime_id="claude_code",
        descriptors=(
            TargetDescriptor(
                target_id="claude_code",
                canonical_name="claude_code",
                profile_env_id="claude_code",
            ),
        ),
        target_factory=_claude_code_target_factory,
        url_proxy_runtime_factory=_claude_code_url_proxy_runtime_factory,
    ),
    RuntimeAdapter(
        runtime_id="openclaw",
        descriptors=(
            TargetDescriptor(
                target_id="openclaw",
                canonical_name="openclaw",
                profile_env_id="openclaw",
            ),
        ),
        target_factory=_openclaw_target_factory,
        url_proxy_runtime_factory=_openclaw_url_proxy_runtime_factory,
    ),
    RuntimeAdapter(
        runtime_id="hermes",
        descriptors=(
            TargetDescriptor(
                target_id="hermes",
                canonical_name="hermes",
                profile_env_id="hermes",
                runtime_generation=_HERMES_RUNTIME_GENERATION,
            ),
        ),
        target_factory=_hermes_target_factory,
        url_proxy_runtime_factory=_hermes_url_proxy_runtime_factory,
    ),
)


@lru_cache(maxsize=1)
def list_runtime_adapters() -> tuple[RuntimeAdapter, ...]:
    return _RUNTIME_ADAPTERS


def get_runtime_adapter(runtime_id: str) -> RuntimeAdapter:
    normalized = str(runtime_id or "").strip()
    for adapter in list_runtime_adapters():
        if adapter.runtime_id == normalized:
            return adapter
    raise ValueError(f"unknown runtime adapter: {runtime_id}")


def get_runtime_adapter_for_target(target_id: str) -> RuntimeAdapter:
    normalized = str(target_id or "").strip()
    for adapter in list_runtime_adapters():
        if any(descriptor.target_id == normalized for descriptor in adapter.descriptors):
            return adapter
    raise ValueError(f"unknown runtime adapter target: {target_id}")


__all__ = [
    "get_runtime_adapter",
    "get_runtime_adapter_for_target",
    "list_runtime_adapters",
]
