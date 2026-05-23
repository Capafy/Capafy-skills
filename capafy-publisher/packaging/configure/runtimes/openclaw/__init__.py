from __future__ import annotations

from packaging.configure.runtimes.lazy_package import make_runtime_package_getattr

_RUNTIME_MODULES = frozenset(
    {
        "auth_profile_materialize",
        "auth_profile_scan_hints",
        "auth_profiles",
        "cron_postprocess",
        "cron_units",
        "provider_confirmation",
        "provider_keys",
        "provider_pairs",
        "provider_rewrite",
        "provider_scan",
        "plugin_config",
        "redaction",
        "scan_hints",
        "selection_paths",
        "selection_units",
        "selection_validation",
        "skill_metadata",
        "target",
        "url_proxy",
        "workspace_common",
        "workspace_paths",
        "workspace_plans",
        "workspace_postprocess",
    }
)


__getattr__ = make_runtime_package_getattr(
    __name__,
    class_exports={
        "OpenClawRuntime": ("url_proxy", "OpenClawRuntime"),
        "OpenClawTarget": ("target", "OpenClawTarget"),
    },
    module_exports=_RUNTIME_MODULES,
)


__all__ = [
    "OpenClawRuntime",
    "OpenClawTarget",
    "auth_profile_materialize",
    "auth_profile_scan_hints",
    "auth_profiles",
    "cron_postprocess",
    "cron_units",
    "provider_confirmation",
    "provider_keys",
    "provider_pairs",
    "provider_rewrite",
    "provider_scan",
    "plugin_config",
    "redaction",
    "scan_hints",
    "selection_paths",
    "selection_units",
    "selection_validation",
    "skill_metadata",
    "target",
    "url_proxy",
    "workspace_common",
    "workspace_paths",
    "workspace_plans",
    "workspace_postprocess",
]
