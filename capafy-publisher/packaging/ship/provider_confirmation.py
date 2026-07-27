from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union

from packaging.configure.staging.review import refresh_reviewed_scan_metadata
from packaging.configure.staging.review_confirmation import reconcile_reviewed_scan_with_platform_confirmation
from packaging._shared.reviewed_scan.io import (
    persist_reviewed_scan,
    read_submitted_config_reviewed_scan_file,
)
from packaging.configure.scan.staging_scan import scan_staging_full
from packaging.configure.staging.strip.removed_generic import remove_unconfirmed_generic_config_values
from packaging.configure.url_proxy.runtime_registry import build_runtime_for_target


def _apply_platform_confirmed_provider_selection(
    *,
    staging_root: Path,
    env_id: str,
    reviewed_scan: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(reviewed_scan, dict):
        return {}
    runtime = build_runtime_for_target(env_id)
    if not runtime.carries_provider_runtime_config:
        return {}
    return runtime.rewrite_confirmed(staging_root, reviewed_scan) or {}


def _apply_confirmed_platform_configuration(
    *,
    staging_root: Path,
    agent_version_id: str,
    env_id: str,
    agent_type: str,
    reviewed_scan: dict[str, Any],
    required_credentials_payload: Union[dict[str, Any], object],
    developer_work_dir_path: Path,
) -> dict[str, Any]:
    if not isinstance(reviewed_scan, dict) or not isinstance(required_credentials_payload, dict):
        return reviewed_scan
    if not required_credentials_payload or not str(staging_root or "").strip() or not staging_root.is_dir():
        return reviewed_scan

    reconciled = reconcile_reviewed_scan_with_platform_confirmation(
        reviewed_scan,
        required_credentials_payload=required_credentials_payload,
    )
    if not isinstance(reconciled, dict):
        return reviewed_scan

    provider_summary = _apply_platform_confirmed_provider_selection(
        staging_root=staging_root,
        env_id=env_id,
        reviewed_scan=reconciled,
    )
    submitted_baseline = read_submitted_config_reviewed_scan_file(
        developer_work_dir_path=developer_work_dir_path,
        agent_version_id=agent_version_id,
    )
    if submitted_baseline and "generic" not in required_credentials_payload:
        required_credentials_payload = dict(required_credentials_payload)
        required_credentials_payload["generic"] = []
    removal_baseline = submitted_baseline or reconciled
    generic_result = remove_unconfirmed_generic_config_values(
        staging_root,
        reviewed_scan=reconciled,
        required_credentials_payload=required_credentials_payload,
        baseline_reviewed_scan=removal_baseline,
    )
    reconciled = generic_result["reviewed_scan"]
    generic_summary = generic_result["summary"]
    if generic_summary.get("generic_config_entries_removed"):
        provider_summary.update(generic_summary)
    if any(provider_summary.values()):
        raw_scan = scan_staging_full(
            staging_root,
            target_name=env_id,
            platform_agent_type=agent_type,
        )
        refreshed = refresh_reviewed_scan_metadata(
            reconciled,
            raw_scan=raw_scan,
            staging_root=staging_root,
            env_id=env_id,
            agent_type=agent_type,
        )
    elif reconciled != reviewed_scan:
        refreshed = refresh_reviewed_scan_metadata(reconciled)
    else:
        return reviewed_scan

    updated_reviewed_scan = refreshed if isinstance(refreshed, dict) else reconciled
    persist_reviewed_scan(updated_reviewed_scan, developer_work_dir_path=developer_work_dir_path)
    return updated_reviewed_scan


def apply_provider_confirmation(
    *,
    agent_version_id: str = "",
    env_id: str = "",
    agent_type: str,
    reviewed_scan: dict[str, Any],
    staging_root: str = "",
    required_credentials_payload: Union[dict[str, Any], object] = None,
    developer_work_dir_path: Optional[Path] = None,
) -> dict[str, Any]:
    if (
        staging_root
        and isinstance(required_credentials_payload, dict)
        and required_credentials_payload
        and developer_work_dir_path is not None
    ):
        reviewed_scan = _apply_confirmed_platform_configuration(
            staging_root=Path(staging_root),
            agent_version_id=agent_version_id,
            env_id=env_id,
            agent_type=agent_type,
            reviewed_scan=reviewed_scan,
            required_credentials_payload=required_credentials_payload,
            developer_work_dir_path=developer_work_dir_path,
        )

    return reviewed_scan


__all__ = ["apply_provider_confirmation"]
