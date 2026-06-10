from __future__ import annotations

from functools import lru_cache
from importlib import import_module

from packaging._shared.runtimes.contracts import RuntimePlugin


_PLUGIN_MODULES = (
    "packaging.runtimes.codex.plugin",
    "packaging.runtimes.claude_code.plugin",
    "packaging.runtimes.openclaw.plugin",
    "packaging.runtimes.hermes.plugin",
)


@lru_cache(maxsize=1)
def list_runtime_plugins() -> tuple[RuntimePlugin, ...]:
    plugins: list[RuntimePlugin] = []
    for module_name in _PLUGIN_MODULES:
        module = import_module(module_name)
        plugin = getattr(module, "PLUGIN", None)
        if isinstance(plugin, RuntimePlugin):
            plugins.append(plugin)
    return tuple(plugins)


@lru_cache(maxsize=1)
def _runtime_plugins_by_id() -> dict[str, RuntimePlugin]:
    return {plugin.runtime_id: plugin for plugin in list_runtime_plugins()}


@lru_cache(maxsize=1)
def _runtime_plugins_by_target_id() -> dict[str, RuntimePlugin]:
    plugins: dict[str, RuntimePlugin] = {}
    for plugin in list_runtime_plugins():
        for descriptor in plugin.descriptors():
            plugins[descriptor.target_id] = plugin
    return plugins


def get_runtime_plugin(runtime_id: str) -> RuntimePlugin:
    normalized = str(runtime_id or "").strip()
    try:
        return _runtime_plugins_by_id()[normalized]
    except KeyError as exc:
        raise ValueError(f"unknown runtime plugin: {runtime_id}") from exc


def get_runtime_plugin_for_target(target_id: str) -> RuntimePlugin:
    normalized = str(target_id or "").strip()
    try:
        return _runtime_plugins_by_target_id()[normalized]
    except KeyError as exc:
        raise ValueError(f"unknown runtime plugin target: {target_id}") from exc


__all__ = [
    "get_runtime_plugin",
    "get_runtime_plugin_for_target",
    "list_runtime_plugins",
]
