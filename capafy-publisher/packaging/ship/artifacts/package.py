from __future__ import annotations

from pathlib import Path
from typing import Any

from packaging._shared.common.constants import WORKSPACE_DOCUMENTS_MANIFEST_NAME
from packaging._shared.contracts.bundle_context import BUNDLE_CONTEXT_NAME, validate_agent_type
from packaging._shared.contracts.reviewed_scan import (
    normalize_reviewed_scan_payload,
    required_list,
    sanitize_reviewed_scan_payload,
    summarize_reviewed_scan_deploy_items,
    validate_reviewed_scan_gate,
)
from packaging._shared.contracts.stage_manifest import STAGE_MANIFEST_NAME, load_stage_manifest
from packaging._shared.reviewed_scan.dispose import reviewed_scan_has_final_dispositions
from packaging.ship.artifacts.archive import build_bundle_archive


def _package_run_online_staging(
    staging_root: Path,
    reviewed_scan: dict,
    output_path: Path,
) -> dict:
    sanitized = sanitize_reviewed_scan_payload(reviewed_scan)
    package_payload = {
        "url_proxy": required_list(sanitized, "url_proxy", label="reviewed_scan"),
        "generic": required_list(sanitized, "generic", label="reviewed_scan"),
    }
    key_items, runtime_values = normalize_reviewed_scan_payload(
        package_payload,
        label="reviewed_scan",
    )
    bundle_result = build_bundle_archive(
        staging_root,
        output_path,
        exclude_paths={
            STAGE_MANIFEST_NAME,
            BUNDLE_CONTEXT_NAME,
            WORKSPACE_DOCUMENTS_MANIFEST_NAME,
        },
        exclude_prefixes=("_scan_only",),
    )
    return {
        "agent_type": "run_online",
        "reviewed_scan": summarize_reviewed_scan_deploy_items(key_items, runtime_values),
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

    stage_manifest = load_stage_manifest(staging_root)
    exclude_prefixes = ["_scan_only"]
    manifest_prefixes = stage_manifest.get("scan_only_prefixes", [])
    if isinstance(manifest_prefixes, list):
        exclude_prefixes.extend(
            str(item).strip().rstrip("/")
            for item in manifest_prefixes
            if str(item).strip()
        )
    bundle_result = build_bundle_archive(
        staging_root,
        output_path,
        exclude_paths={BUNDLE_CONTEXT_NAME, STAGE_MANIFEST_NAME},
        exclude_prefixes=tuple(dict.fromkeys(exclude_prefixes)),
    )
    return {
        "agent_type": "download",
        "bundle": bundle_result,
    }


def run_artifact_package(
    *,
    staging_root: str,
    reviewed_scan: dict[str, Any],
    bundle_path: str,
    agent_type: str,
) -> dict[str, Any]:
    staging = Path(staging_root)
    output_path = Path(bundle_path)
    if validate_agent_type(agent_type) == "run_online":
        return _package_run_online_staging(staging, reviewed_scan, output_path)
    return _package_download_staging(staging, reviewed_scan, output_path)


__all__ = ["run_artifact_package"]
