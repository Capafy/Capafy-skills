from __future__ import annotations

from packaging.configure.url_proxy.base import RuntimeContract
from packaging.runtimes.adapters import get_runtime_adapter_for_target


def build_runtime_for_target(target_id: str) -> RuntimeContract:
    adapter = get_runtime_adapter_for_target(target_id)
    runtime = adapter.url_proxy_runtime_factory()
    if not isinstance(runtime, RuntimeContract):
        raise TypeError(f"invalid URL Proxy runtime for target: {target_id}")
    return runtime


__all__ = ["build_runtime_for_target"]
