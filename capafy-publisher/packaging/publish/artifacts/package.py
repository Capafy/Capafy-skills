from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from packaging.publish.artifacts.bundle_context import validate_agent_type
from packaging.publish.reviewed_scan import (
    sanitize_reviewed_scan_payload,
    validate_reviewed_scan_gate,
)
from packaging.publish.reviewed_scan import reviewed_scan_has_final_dispositions
from packaging.publish.artifacts.archive import build_bundle_archive


def _package_run_online_staging(
    staging_root: Path,
    output_path: Path,
) -> dict:
    bundle_result = build_bundle_archive(
        staging_root,
        output_path,
    )
    return {
        "agent_type": "run_online",
        "bundle": bundle_result,
    }


def _package_download_staging(
    staging_root: Path,
    reviewed_scan: dict,
    output_path: Path,
) -> dict:
    package_payload = sanitize_reviewed_scan_payload(reviewed_scan)
    validate_reviewed_scan_gate(package_payload, label="reviewed_scan")
    if not reviewed_scan_has_final_dispositions(package_payload):
        raise ValueError("download package requires reviewed_scan payload with final_disposition for every item")

    bundle_result = build_bundle_archive(
        staging_root,
        output_path,
    )
    return {
        "agent_type": "download",
        "bundle": bundle_result,
    }


def run_artifact_package(
    *,
    staging_root: str,
    reviewed_scan: Optional[dict[str, Any]],
    bundle_path: str,
    agent_type: str,
) -> dict[str, Any]:
    staging = Path(staging_root)
    output_path = Path(bundle_path)
    if validate_agent_type(agent_type) == "run_online":
        return _package_run_online_staging(staging, output_path)
    if not isinstance(reviewed_scan, dict):
        raise ValueError("download package requires reviewed_scan")
    return _package_download_staging(staging, reviewed_scan, output_path)


__all__ = ["run_artifact_package"]
