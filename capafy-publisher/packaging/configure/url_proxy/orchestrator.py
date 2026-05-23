from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from packaging.configure.contracts import UrlProxyPair

from packaging._shared.common.process_env import collect_publish_process_env, url_proxy_os_fallback_names
from packaging.configure.url_proxy.base import RuntimeContract, ScanContext
from packaging.configure.url_proxy.merge import (
    collect_claimed_process_env_names,
    dedupe_cross_source_pairs,
    dedupe_fallback_generic_entries,
)
from packaging.configure.url_proxy.runtime_selection import (
    is_runtime_applicable,
    resolve_target_id,
    runtime_context_target_id,
    runtime_owned_structured_pair,
)
from packaging.configure.url_proxy.runtime_registry import BUILTIN_RUNTIMES

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UrlProxyBuildResult:
    url_proxy_pairs: list["UrlProxyPair"]
    claimed_field_names: frozenset[str]
    fallback_generic_entries: list[dict] = field(default_factory=list)


def build_url_proxy_phase(
    staging_root,
    *,
    env_id: str | None = None,
    process_env: Mapping[str, str] | None = None,
    stage_plan: Any = None,
    user_home=None,
    platform_agent_type: str = "run_online",
) -> UrlProxyBuildResult:
    from packaging.configure.url_proxy.structured_scanner import (
        rewrite_structured_pairs,
        run_structured_url_proxy_scan,
    )

    if process_env is None:
        target_id = resolve_target_id(env_id) if env_id is not None else None
        fallback_names = url_proxy_os_fallback_names(target_id)
        process_env = collect_publish_process_env(
            user_home=user_home,
            os_fallback_names=fallback_names,
        )

    context_target_id = runtime_context_target_id(env_id)
    ctx = ScanContext(
        staging_root=staging_root,
        process_env=process_env,
        stage_plan=stage_plan,
        user_home=user_home,
        target_id=context_target_id,
    )

    runtime_collected: list[tuple[RuntimeContract, list[UrlProxyPair]]] = []
    for runtime in BUILTIN_RUNTIMES:
        if not is_runtime_applicable(runtime, env_id):
            logger.debug("skip runtime %s (not applicable for %s)", runtime.runtime_id, env_id)
            continue
        runtime.prepare(ctx)
        candidates = runtime.scan(ctx)
        if not candidates:
            continue
        pairs = runtime.pair(candidates)
        if pairs:
            runtime_collected.append((runtime, pairs))

    if env_id is not None and str(env_id).strip():
        structured_target_name = resolve_target_id(env_id)
        contract_id_for_structured = str(env_id).strip() or "STRUCTURED"
        structured_result = run_structured_url_proxy_scan(
            staging_root,
            target_name=structured_target_name,
            platform_agent_type=platform_agent_type,
            default_contract_id=contract_id_for_structured,
        )
    else:
        from packaging.configure.url_proxy.structured_scanner import (
            StructuredUrlProxyScanResult,
        )
        structured_result = StructuredUrlProxyScanResult(
            pairs=[],
            fallback_generic_entries=[],
            claimed_field_names=frozenset(),
        )

    runtime_pairs: list[UrlProxyPair] = []
    for runtime, pairs in runtime_collected:
        runtime.rewrite(staging_root, pairs)
        runtime_pairs.extend(pairs)

    structured_pairs = [
        pair for pair in structured_result.pairs
        if not runtime_owned_structured_pair(pair, target_id=context_target_id)
    ]
    rewrite_structured_pairs(staging_root, structured_pairs)

    all_pairs, duplicate_count = dedupe_cross_source_pairs(runtime_pairs, structured_pairs)
    if duplicate_count:
        logger.debug(
            "build_url_proxy_phase: deduped %d cross-source duplicate pairs",
            duplicate_count,
        )

    deduped_fallback = dedupe_fallback_generic_entries(
        structured_result.fallback_generic_entries,
        runtime_pairs,
    )

    claimed = collect_claimed_process_env_names(all_pairs)

    return UrlProxyBuildResult(
        url_proxy_pairs=all_pairs,
        claimed_field_names=claimed,
        fallback_generic_entries=deduped_fallback,
    )


__all__ = [
    "UrlProxyBuildResult",
    "build_url_proxy_phase",
    "is_runtime_applicable",
]
