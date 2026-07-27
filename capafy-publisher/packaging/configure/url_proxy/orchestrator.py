from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from packaging.configure.staging.provider_runtime_config import ProviderRuntimeConfigContext
    from packaging.configure.contracts import UrlProxyPair

from packaging.configure.provider_runtime_config.environment import collect_provider_environment, url_proxy_os_fallback_names
from packaging.configure.url_proxy.base import RuntimeContract, ScanContext
from packaging.configure.url_proxy.runtime_registry import build_runtime_for_target
from packaging.runtimes.registry import get_target_descriptor


@dataclass(frozen=True)
class UrlProxyBuildResult:
    url_proxy_pairs: list["UrlProxyPair"]


def build_url_proxy_phase(
    staging_root,
    *,
    env_id: Optional[str] = None,
    process_env: Optional[Mapping[str, str]] = None,
    stage_plan: Any = None,
    user_home=None,
    provider_config_context: Optional["ProviderRuntimeConfigContext"] = None,
    runtime: Optional[RuntimeContract] = None,
) -> UrlProxyBuildResult:
    normalized_env_id = str(env_id or "").strip()
    if not normalized_env_id:
        raise ValueError("env_id is required for URL Proxy")
    target_id = get_target_descriptor(normalized_env_id).target_id
    current_runtime = runtime or build_runtime_for_target(target_id)

    if process_env is None:
        fallback_names = url_proxy_os_fallback_names(target_id, runtime=current_runtime)
        process_env = collect_provider_environment(
            user_home=user_home,
            os_fallback_names=fallback_names,
        )

    ctx = ScanContext(
        staging_root=staging_root,
        process_env=process_env,
        stage_plan=stage_plan,
        user_home=user_home,
        provider_config_context=provider_config_context,
    )

    managed_config_flow = current_runtime.carries_provider_runtime_config
    if managed_config_flow:
        current_runtime.prepare(ctx)
    candidates = current_runtime.scan(ctx)
    runtime_pairs = current_runtime.pair(candidates) if candidates else []

    if managed_config_flow and runtime_pairs:
        current_runtime.rewrite(staging_root, runtime_pairs)

    return UrlProxyBuildResult(
        url_proxy_pairs=runtime_pairs,
    )


__all__ = [
    "UrlProxyBuildResult",
    "build_url_proxy_phase",
]
