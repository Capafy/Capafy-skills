from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from packaging.configure.contracts import DeepScanFindingsInput, ReviewedScanBuildInput
from packaging._shared.common.process_env import collect_publish_process_env, url_proxy_os_fallback_names
from packaging.configure.staging.env_preprocess import RuntimeEnvContext, preprocess_runtime_env_sources
from packaging.configure.staging.review import build_review_binding
from packaging.configure.staging.source_boundary import filter_generic_values_for_packaged_sources


def build_cloud_hosted_reviewed_scan(
    *,
    staging_root_p: Path,
    staging_root: str,
    env_id: str,
    agent_type: str,
    stage_plan: Any,
    deep_scan_findings: Optional[DeepScanFindingsInput] = None,
) -> tuple[dict, dict, dict]:
    from packaging.configure.sensitive.deep_scan_findings import deep_scan_findings_to_reviewed_inputs_for_staging
    from packaging.configure.env_var.orchestrator import run_general_scan
    from packaging.configure.scan.staging_scan import scan_staging_full
    from packaging.configure.sensitive.text_redact import clean_special_files_in_staging
    from packaging.configure.staging.strip.fallback import apply_strip
    from packaging.configure.staging.strip.generic import apply_generic_to_staging
    from packaging.configure.url_proxy.merge import filter_url_proxy_claimed_reviewed_input
    from packaging.configure.url_proxy.orchestrator import build_url_proxy_phase

    deep_scan_findings = deep_scan_findings or DeepScanFindingsInput()
    process_env = collect_publish_process_env()
    env_context = RuntimeEnvContext(process_env=process_env)
    url_proxy_process_env = collect_publish_process_env(
        os_fallback_names=url_proxy_os_fallback_names(env_id),
    )
    preprocessed_env_names = preprocess_runtime_env_sources(
        staging_root_p,
        env_id=env_id,
        env_context=env_context,
    )

    url_proxy_result = build_url_proxy_phase(
        staging_root_p,
        env_id=env_id,
        process_env=url_proxy_process_env,
        stage_plan=stage_plan,
        platform_agent_type=agent_type,
        env_context=env_context,
    )
    env_context.apply_staged_dotenv_consumption(staging_root_p)
    url_proxy_pairs = url_proxy_result.url_proxy_pairs
    excluded_process_env_names = frozenset({
        *url_proxy_result.claimed_field_names,
        *preprocessed_env_names,
    })

    staging_scan_result = scan_staging_full(
        staging_root_p,
        target_name=env_id,
        platform_agent_type=agent_type,
    )
    raw_scan = staging_scan_result.raw_scan

    if url_proxy_result.fallback_generic_entries:
        raw_scan = dict(raw_scan)
        raw_scan["generic"] = list(raw_scan.get("generic") or []) + list(
            url_proxy_result.fallback_generic_entries
        )

    general_result = run_general_scan(
        raw_scan,
        process_env=process_env,
        excluded_process_env_names=excluded_process_env_names,
        referenced_env_names=staging_scan_result.referenced_env_names,
        env_url_hints=staging_scan_result.env_url_hints,
    )

    reviewed_scan_input = ReviewedScanBuildInput(
        url_proxy_pairs=tuple(url_proxy_pairs),
        generic_values=general_result.generic_values,
        env_vars=general_result.env_vars,
        excludes=general_result.excludes,
    )
    if deep_scan_findings.generic or deep_scan_findings.env_var:
        finding_generic_values, finding_env_vars = deep_scan_findings_to_reviewed_inputs_for_staging(
            staging_root_p,
            deep_scan_findings,
            agent_type=agent_type,
        )
        if finding_generic_values or finding_env_vars:
            reviewed_scan_input = ReviewedScanBuildInput(
                url_proxy_pairs=reviewed_scan_input.url_proxy_pairs,
                generic_values=tuple([*reviewed_scan_input.generic_values, *finding_generic_values]),
                env_vars=tuple([*reviewed_scan_input.env_vars, *finding_env_vars]),
                excludes=reviewed_scan_input.excludes,
            )

    reviewed_scan_input = filter_url_proxy_claimed_reviewed_input(reviewed_scan_input)

    packaged_generic_values = filter_generic_values_for_packaged_sources(
        reviewed_scan_input.generic_values,
        staging_root=staging_root_p,
        excluded_relpaths=(excluded.source for excluded in reviewed_scan_input.excludes),
        agent_type=agent_type,
    )
    if packaged_generic_values != reviewed_scan_input.generic_values:
        reviewed_scan_input = ReviewedScanBuildInput(
            url_proxy_pairs=reviewed_scan_input.url_proxy_pairs,
            generic_values=packaged_generic_values,
            env_vars=reviewed_scan_input.env_vars,
            excludes=reviewed_scan_input.excludes,
        )

    apply_generic_to_staging(staging_root_p, reviewed_scan_input.generic_values)
    clean_special_files_in_staging(staging_root_p)
    apply_strip(staging_root_p, reviewed_scan_input)

    review_binding = build_review_binding(
        raw_scan=raw_scan,
        staging_root=staging_root,
        env_id=env_id,
        agent_type=agent_type,
    )
    reviewed_scan = reviewed_scan_input.to_reviewed_scan(review_binding=review_binding)

    return reviewed_scan, raw_scan, review_binding


__all__ = [
    "build_cloud_hosted_reviewed_scan",
]
