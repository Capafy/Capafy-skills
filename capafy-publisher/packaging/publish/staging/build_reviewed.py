from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from packaging.common.constants import DEFAULT_STAGING_PATH, DEVELOPER_WORK_DIR_PATH
from packaging.common.fs import cleanup_staging_root
from packaging.common.fs import read_text
from packaging.common.cli import build_publish_error
from packaging.publish.selection.explicit_skill import (
    explicit_skill_from_manifest_extra,
    merge_external_skill_bindings_into_selection_groups,
    merge_explicit_skill_into_selection_groups,
)
from packaging.publish.security.deep_scan_payload import build_deep_scan_payload
from packaging.publish.staging.review import (
    build_review_binding,
    build_reviewed_scan_from_input,
    build_reviewed_scan_from_scan,
)
from packaging.publish.reviewed_scan import load_reviewed_scan_path, persist_reviewed_scan
from packaging.publish.security.scan.staging_scan import scan_staging_full
from packaging.publish.staging.selection_payload import skills_plan_from_selection_groups
from packaging.publish.staging.pipeline import run_stage_pipeline
from packaging.runtime.contracts import DeepScanFindingsInput, ReviewedScanBuildInput
from packaging.publish.security.scan.env_reference_scan import collect_referenced_env_names
from packaging.publish.platform.url_proxy_environment import (
    collect_provider_environment,
    url_proxy_os_fallback_names,
)
from packaging.publish.staging.source_boundary import filter_generic_values_for_packaged_sources
from packaging.publish.security.scan.entries import filter_generic_values
from packaging.runtime.registry import build_provider_runtime_for_target


@dataclass(frozen=True)
class ReviewedScanResult:
    staging_root: str
    reviewed_scan_path: str
    reviewed_scan: dict[str, Any]
    staging_digest: str
    suggested_environment_variable_names: tuple[str, ...] = ()


def build_run_online_reviewed_scan(
    *,
    staging_root: Path,
    env_id: str,
    stage_plan: Any,
    deep_scan_findings: Optional[DeepScanFindingsInput] = None,
) -> tuple[dict, dict, dict]:
    """Build the hosted review payload in the shared stage/review pipeline."""
    from packaging.publish.security.sensitive.deep_scan_findings import deep_scan_findings_to_generic_values_for_staging
    from packaging.publish.security.sensitive.text_redact import clean_special_files_in_staging
    from packaging.publish.staging.strip import apply_strip
    from packaging.publish.platform.url_proxy import build_url_proxy_phase

    deep_scan_findings = deep_scan_findings or DeepScanFindingsInput()
    runtime = build_provider_runtime_for_target(env_id)
    url_proxy_environment_names = url_proxy_os_fallback_names(env_id, runtime=runtime)
    url_proxy_process_env = collect_provider_environment(
        names=url_proxy_environment_names,
        os_fallback_names=url_proxy_environment_names,
    )

    url_proxy_result = build_url_proxy_phase(
        staging_root,
        env_id=env_id,
        process_env=url_proxy_process_env,
        stage_plan=stage_plan,
        runtime=runtime,
    )
    raw_scan = scan_staging_full(
        staging_root,
        target_name=env_id,
        stage_plan=stage_plan,
    )
    raw_generic = raw_scan.get("generic", [])
    generic_values = tuple(
        filter_generic_values(raw_generic if isinstance(raw_generic, list) else [])
    )
    reviewed_scan_input = ReviewedScanBuildInput(
        url_proxy_pairs=tuple(url_proxy_result.url_proxy_pairs),
        generic_values=generic_values,
    )

    if deep_scan_findings.generic:
        finding_generic_values = deep_scan_findings_to_generic_values_for_staging(
            staging_root,
            deep_scan_findings,
            agent_type="run_online",
        )
        if finding_generic_values:
            reviewed_scan_input = ReviewedScanBuildInput(
                url_proxy_pairs=reviewed_scan_input.url_proxy_pairs,
                generic_values=(
                    *reviewed_scan_input.generic_values,
                    *finding_generic_values,
                ),
            )

    packaged_generic_values = filter_generic_values_for_packaged_sources(
        reviewed_scan_input.generic_values,
        staging_root=staging_root,
        agent_type="run_online",
    )
    if packaged_generic_values != reviewed_scan_input.generic_values:
        reviewed_scan_input = ReviewedScanBuildInput(
            url_proxy_pairs=reviewed_scan_input.url_proxy_pairs,
            generic_values=packaged_generic_values,
        )

    clean_special_files_in_staging(staging_root)
    apply_strip(staging_root, reviewed_scan_input.generic_values)
    review_binding = build_review_binding(
        raw_scan=raw_scan,
        staging_root=staging_root,
        env_id=env_id,
        agent_type="run_online",
    )
    reviewed_scan = build_reviewed_scan_from_input(
        reviewed_scan_input,
        review_binding=review_binding,
    )
    return reviewed_scan, raw_scan, review_binding


def _selected_skill_environment_variable_names(
    staging_root: Path,
    stage_payload: dict[str, Any],
) -> tuple[str, ...]:
    raw_paths = stage_payload.get("selected_skill_paths")
    if not isinstance(raw_paths, list):
        return ()
    root = staging_root.resolve()
    names: set[str] = set()
    for raw_path in raw_paths:
        relpath = str(raw_path or "").strip().replace("\\", "/").strip("/")
        if not relpath or relpath == ".." or relpath.startswith("../") or "/../" in relpath:
            continue
        skill_path = (root / relpath).resolve()
        if skill_path != root and root not in skill_path.parents:
            continue
        files = [skill_path] if skill_path.is_file() else (
            sorted(path for path in skill_path.rglob("*") if path.is_file())
            if skill_path.is_dir()
            else []
        )
        for path in files:
            text, _encoding = read_text(path)
            if text is None:
                continue
            referenced_names, _url_hints = collect_referenced_env_names(text)
            names.update(referenced_names)
    return tuple(sorted(names))


def build_staging_and_reviewed_scan(
    *,
    env_id: str,
    runtime_dir: str,
    agent_type: str,
    selection_groups: dict,
    deep_scan_findings: Optional[DeepScanFindingsInput] = None,
    developer_work_dir_path: Path = DEVELOPER_WORK_DIR_PATH,
    default_staging_path: str = DEFAULT_STAGING_PATH,
) -> tuple[Optional[ReviewedScanResult], Optional[dict]]:
    deep_scan_findings = deep_scan_findings or DeepScanFindingsInput()
    normalized_runtime_dir = str(runtime_dir or "").strip()
    if not normalized_runtime_dir:
        return None, build_publish_error(
            error="runtime_dir is required",
            failed_step="stage",
            blocking_category="missing_runtime_dir",
            developer_next_steps=[
                "Rerun publish-init with --env and --runtime-dir, then complete the platform confirmation again.",
            ],
            next_step="rerun_publish_init_with_runtime_dir",
            env_id=env_id,
            agent_type=agent_type,
        )
    skills_plan_json = skills_plan_from_selection_groups(
        selection_groups,
        agent_type=agent_type,
    )
    staging_root_path = Path(default_staging_path)
    if staging_root_path.exists():
        cleanup_staging_root(staging_root_path)

    stage_result = run_stage_pipeline(
        staging_root_path,
        runtime_dir=normalized_runtime_dir,
        target_name=env_id,
        skills_plan_json=skills_plan_json,
    )
    stage_payload = stage_result.payload
    staging_root = str(stage_payload.get("staging_path", "")).strip()
    if not staging_root:
        return None, build_publish_error(
            error="stage did not return a staging_path",
            failed_step="stage",
            blocking_category="invalid_stage_payload",
            developer_next_steps=[
                "Inspect the stage payload and fix the stage precondition, then rerun publish-submit.",
            ],
            next_step="fix_stage_precondition_then_retry",
            stage_payload=stage_payload,
        )

    staging_root_p = Path(staging_root)
    stage_plan = stage_result.stage_plan
    is_run_online = agent_type == "run_online"

    if is_run_online:
        reviewed_scan, raw_scan, review_binding = build_run_online_reviewed_scan(
            staging_root=staging_root_p,
            env_id=env_id,
            stage_plan=stage_plan,
            deep_scan_findings=deep_scan_findings,
        )
    else:
        raw_scan = scan_staging_full(
            staging_root_p,
            target_name=env_id,
        )
        review_binding = build_review_binding(
            raw_scan=raw_scan,
            staging_root=staging_root,
            env_id=env_id,
            agent_type=agent_type,
        )
        reviewed_scan = build_reviewed_scan_from_scan(
            raw_scan,
            review_binding=review_binding,
            staging_root=staging_root_p,
        )
        if deep_scan_findings.generic:
            from packaging.publish.security.sensitive.deep_scan_findings import (
                deep_scan_findings_to_generic_values_for_staging,
            )

            reviewed_scan["generic"].extend(
                build_reviewed_scan_from_input(
                    ReviewedScanBuildInput(
                        url_proxy_pairs=(),
                        generic_values=deep_scan_findings_to_generic_values_for_staging(
                            staging_root_p,
                            deep_scan_findings,
                            agent_type=agent_type,
                        ),
                    ),
                    review_binding=review_binding,
                )["generic"]
            )

    suggested_environment_variable_names = (
        _selected_skill_environment_variable_names(staging_root_p, stage_payload)
        if is_run_online
        else ()
    )
    reviewed_scan_path = load_reviewed_scan_path(developer_work_dir_path=developer_work_dir_path)
    persist_reviewed_scan(reviewed_scan, developer_work_dir_path=developer_work_dir_path)

    return ReviewedScanResult(
        staging_root=staging_root,
        reviewed_scan_path=reviewed_scan_path,
        reviewed_scan=reviewed_scan,
        staging_digest=str(review_binding.get("staging_digest", "") or "").strip(),
        suggested_environment_variable_names=suggested_environment_variable_names,
    ), None


def build_prepare_staging(
    ctx: Any,
) -> tuple[Optional[ReviewedScanResult], Optional[tuple[dict[str, Any], int]]]:
    latest_state = ctx.latest_state
    manifest_extra = ctx.manifest.extra
    selection_groups = merge_explicit_skill_into_selection_groups(
        latest_state.selection_groups,
        explicit_skill_from_manifest_extra(manifest_extra),
    )
    selection_groups = merge_external_skill_bindings_into_selection_groups(
        selection_groups,
        manifest_extra.get("external_skill_bindings") if isinstance(manifest_extra, dict) else None,
    )
    result, build_error = build_staging_and_reviewed_scan(
        env_id=latest_state.env_id,
        runtime_dir=ctx.manifest.runtime_dir,
        agent_type=latest_state.agent_type,
        selection_groups=selection_groups,
        deep_scan_findings=getattr(ctx, "deep_scan_findings", ()),
    )
    if build_error is not None:
        return None, (build_error, 1)
    assert result is not None
    if not ctx.deep_scan:
        return result, None
    return None, (
        build_deep_scan_payload(
            agent_id=ctx.agent_id,
            agent_version_id=latest_state.agent_version_id,
            env_id=latest_state.env_id,
            agent_type=latest_state.agent_type,
            staging_root=result.staging_root,
            reviewed_scan=result.reviewed_scan,
        ),
        0,
    )


__all__ = [
    "ReviewedScanResult",
    "build_prepare_staging",
    "build_run_online_reviewed_scan",
    "build_staging_and_reviewed_scan",
]
