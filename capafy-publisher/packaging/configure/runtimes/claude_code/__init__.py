from __future__ import annotations

from packaging.configure.runtimes.lazy_package import make_runtime_package_getattr

_RUNTIME_MODULES = frozenset({"auth", "scan_hints", "settings_json", "target", "url_proxy"})


__getattr__ = make_runtime_package_getattr(
    __name__,
    class_exports={
        "ClaudeCodeRuntime": ("url_proxy", "ClaudeCodeRuntime"),
        "ClaudeCodeTarget": ("target", "ClaudeCodeTarget"),
    },
    module_exports=_RUNTIME_MODULES,
)


__all__ = [
    "ClaudeCodeRuntime",
    "ClaudeCodeTarget",
    "auth",
    "scan_hints",
    "settings_json",
    "target",
    "url_proxy",
]
