from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from packaging.configure.contracts import DeepScanFindingsInput, ReviewedScanBuildInput
from packaging.configure.provider_runtime_config.environment import (
    collect_provider_environment,
    url_proxy_os_fallback_names,
)
from packaging.configure.staging.provider_runtime_config import (
    ProviderRuntimeConfigContext,
    prune_proxy_environment_sources,
)
from packaging.configure.staging.review import build_review_binding
from packaging.configure.staging.source_boundary import filter_generic_values_for_packaged_sources
from packaging.configure.reviewed_scan_builder import build_reviewed_scan_from_input
from packaging.configure.url_proxy.runtime_registry import build_runtime_for_target


def build_cloud_hosted_reviewed_scan(
    *,
    staging_root_p: Path,
    staging_root: str,
    env_id: str,
    agent_type: str,
    stage_plan: Any,
    deep_scan_findings: Optional[DeepScanFindingsInput] = None,
) -> tuple[dict, dict, dict]:
    from packaging.configure.sensitive.deep_scan_findings import deep_scan_findings_to_generic_values_for_staging
    from packaging.configure.general_scan import run_general_scan
    from packaging.configure.scan.staging_scan import scan_staging_full
    from packaging.configure.sensitive.text_redact import clean_special_files_in_staging
    from packaging.configure.staging.strip.fallback import apply_strip
    from packaging.configure.url_proxy.merge import filter_url_proxy_claimed_reviewed_input
    from packaging.configure.url_proxy.orchestrator import build_url_proxy_phase

    deep_scan_findings = deep_scan_findings or DeepScanFindingsInput()
    runtime = build_runtime_for_target(env_id)
    provider_config_context: Optional[ProviderRuntimeConfigContext] = None
    if runtime.carries_provider_runtime_config:
        provider_config_context = ProviderRuntimeConfigContext(
            process_env=collect_provider_environment(),
        )
        prune_proxy_environment_sources(staging_root_p)
        runtime.prepare_provider_runtime_config(
            staging_root_p,
            provider_config_context=provider_config_context,
        )
    url_proxy_environment_names = url_proxy_os_fallback_names(env_id, runtime=runtime)
    url_proxy_process_env = collect_provider_environment(
        names=(
            url_proxy_environment_names
            if not runtime.carries_provider_runtime_config
            else None
        ),
        os_fallback_names=url_proxy_environment_names,
    )

    url_proxy_result = build_url_proxy_phase(
        staging_root_p,
        env_id=env_id,
        process_env=url_proxy_process_env,
        stage_plan=stage_plan,
        provider_config_context=provider_config_context,
        runtime=runtime,
    )
    if provider_config_context is not None:
        provider_config_context.apply_staged_dotenv_consumption(staging_root_p)
    url_proxy_pairs = url_proxy_result.url_proxy_pairs
    raw_scan = scan_staging_full(
        staging_root_p,
        target_name=env_id,
        platform_agent_type=agent_type,
        stage_plan=stage_plan,
    )

    general_result = run_general_scan(raw_scan)

    reviewed_scan_input = ReviewedScanBuildInput(
        url_proxy_pairs=tuple(url_proxy_pairs),
        generic_values=general_result.generic_values,
    )
    if deep_scan_findings.generic:
        finding_generic_values = deep_scan_findings_to_generic_values_for_staging(
            staging_root_p,
            deep_scan_findings,
            agent_type=agent_type,
        )
        if finding_generic_values:
            reviewed_scan_input = ReviewedScanBuildInput(
                url_proxy_pairs=reviewed_scan_input.url_proxy_pairs,
                generic_values=tuple([*reviewed_scan_input.generic_values, *finding_generic_values]),
            )

    if runtime.carries_provider_runtime_config:
        reviewed_scan_input = filter_url_proxy_claimed_reviewed_input(
            reviewed_scan_input,
            runtime=runtime,
        )

    packaged_generic_values = filter_generic_values_for_packaged_sources(
        reviewed_scan_input.generic_values,
        staging_root=staging_root_p,
        agent_type=agent_type,
    )
    if packaged_generic_values != reviewed_scan_input.generic_values:
        reviewed_scan_input = ReviewedScanBuildInput(
            url_proxy_pairs=reviewed_scan_input.url_proxy_pairs,
            generic_values=packaged_generic_values,
        )

    clean_special_files_in_staging(staging_root_p)
    apply_strip(staging_root_p, reviewed_scan_input)

    review_binding = build_review_binding(
        raw_scan=raw_scan,
        staging_root=staging_root,
        env_id=env_id,
        agent_type=agent_type,
    )
    reviewed_scan = build_reviewed_scan_from_input(reviewed_scan_input, review_binding=review_binding)
    if runtime.carries_provider_runtime_config:
        runtime.validate_review_consistency(staging_root_p, reviewed_scan=reviewed_scan)

    return reviewed_scan, raw_scan, review_binding


__all__ = [
    "build_cloud_hosted_reviewed_scan",
]
