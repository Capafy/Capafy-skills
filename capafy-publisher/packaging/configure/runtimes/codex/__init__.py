from __future__ import annotations

from packaging.configure.runtimes.lazy_package import make_runtime_package_getattr

_RUNTIME_MODULES = frozenset({
    "auth",
    "config_state",
    "dotenv",
    "local_files",
    "provider",
    "provider_config",
    "provider_scan",
    "rewrite",
    "scan_hints",
    "target",
    "url_proxy",
})


__getattr__ = make_runtime_package_getattr(
    __name__,
    class_exports={
        "CodexRuntime": ("url_proxy", "CodexRuntime"),
        "CodexTarget": ("target", "CodexTarget"),
    },
    module_exports=_RUNTIME_MODULES,
)


__all__ = [
    "CodexRuntime",
    "CodexTarget",
    "auth",
    "config_state",
    "dotenv",
    "local_files",
    "provider",
    "provider_config",
    "provider_scan",
    "scan_hints",
    "rewrite",
    "target",
    "url_proxy",
]
