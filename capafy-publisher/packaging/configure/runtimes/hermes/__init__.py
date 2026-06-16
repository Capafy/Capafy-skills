from __future__ import annotations

from packaging.configure.runtimes.lazy_package import make_runtime_package_getattr

_RUNTIME_MODULES = frozenset({
    "api_modes",
    "auth_profile_materialize",
    "auth_profiles",
    "config",
    "provider_blocks",
    "provider_confirmation",
    "provider_normalize",
    "provider_pairs",
    "provider_refs",
    "provider_rewrite",
    "provider_scan",
    "review_consistency",
    "url_proxy",
})


__getattr__ = make_runtime_package_getattr(
    __name__,
    class_exports={
        "HermesRuntime": ("url_proxy", "HermesRuntime"),
    },
    module_exports=_RUNTIME_MODULES,
)


__all__ = [
    "HermesRuntime",
    "api_modes",
    "auth_profile_materialize",
    "auth_profiles",
    "config",
    "provider_blocks",
    "provider_confirmation",
    "provider_normalize",
    "provider_pairs",
    "provider_refs",
    "provider_rewrite",
    "provider_scan",
    "review_consistency",
    "url_proxy",
]
