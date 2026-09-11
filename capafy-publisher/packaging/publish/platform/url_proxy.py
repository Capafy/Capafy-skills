from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from packaging.runtime.contracts import LlmRoute, RuntimeContract, ScanContext
from packaging.publish.platform.url_proxy_environment import collect_provider_environment, url_proxy_os_fallback_names
from packaging.runtime.registry import build_provider_runtime_for_target
from packaging.runtime.registry import get_target_descriptor


@dataclass(frozen=True)
class UrlProxyBuildResult:
    url_proxy_pairs: list[LlmRoute]

    @property
    def routes(self) -> list[LlmRoute]:
        return self.url_proxy_pairs


def build_url_proxy_phase(
    staging_root,
    *,
    env_id: Optional[str] = None,
    process_env: Optional[Mapping[str, str]] = None,
    stage_plan: Any = None,
    user_home=None,
    runtime: Optional[RuntimeContract] = None,
) -> UrlProxyBuildResult:
    normalized_env_id = str(env_id or "").strip()
    if not normalized_env_id:
        raise ValueError("env_id is required for URL Proxy")
    target_id = get_target_descriptor(normalized_env_id).target_id
    current_runtime = runtime or build_provider_runtime_for_target(target_id)

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
    )

    runtime_routes = current_runtime.routes(ctx)

    return UrlProxyBuildResult(
        url_proxy_pairs=runtime_routes,
    )


__all__ = [
    "UrlProxyBuildResult",
    "build_url_proxy_phase",
]
