from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from packaging._shared.common.constants import DEFAULT_STAGING_PATH, DEVELOPER_WORK_DIR_PATH
from packaging._shared.common.fs import cleanup_staging_root
from packaging._shared.common.cli import build_publish_error
from packaging.configure.staging.review import build_review_binding, build_reviewed_scan_from_scan
from packaging._shared.reviewed_scan.io import load_reviewed_scan_path, persist_reviewed_scan
from packaging.configure.scan.staging_scan import scan_staging_full
from packaging.configure.staging.selection_payload import skills_plan_from_selection_groups
from packaging.configure.staging.pipeline import StageBuildResult, run_stage_pipeline
from packaging.configure.cloud_hosted_pipeline import build_cloud_hosted_reviewed_scan
from packaging.configure.contracts import DeepScanFindingsInput


@dataclass(frozen=True)
class ReviewedScanResult:
    staging_root: str
    reviewed_scan_path: str
    raw_scan: dict[str, Any]
    reviewed_scan: dict[str, Any]
    review_binding: dict[str, str]
    stage_payload: dict[str, Any]
    stage_plan: Any = None


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
                "Inspect the stage payload and fix the stage precondition, then rerun publish-configure.",
            ],
            next_step="fix_stage_precondition_then_retry",
            stage_payload=stage_payload,
        )

    staging_root_p = Path(staging_root)
    stage_plan = stage_result.stage_plan
    is_run_online = str(agent_type or "").strip() == "run_online"

    if is_run_online:
        reviewed_scan, raw_scan, review_binding = build_cloud_hosted_reviewed_scan(
            staging_root_p=staging_root_p,
            staging_root=staging_root,
            env_id=env_id,
            agent_type=agent_type,
            stage_plan=stage_plan,
            deep_scan_findings=deep_scan_findings,
        )
    else:

        raw_scan = scan_staging_full(
            staging_root_p,
            target_name=env_id,
            platform_agent_type=agent_type,
        ).raw_scan
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

    reviewed_scan_path = load_reviewed_scan_path(developer_work_dir_path=developer_work_dir_path)
    persist_reviewed_scan(reviewed_scan, developer_work_dir_path=developer_work_dir_path)

    return ReviewedScanResult(
        staging_root=staging_root,
        reviewed_scan_path=reviewed_scan_path,
        raw_scan=raw_scan,
        reviewed_scan=reviewed_scan,
        review_binding=review_binding,
        stage_payload=stage_payload,
        stage_plan=stage_plan,
    ), None


__all__ = [
    "ReviewedScanResult",
    "StageBuildResult",
    "build_staging_and_reviewed_scan",
]
