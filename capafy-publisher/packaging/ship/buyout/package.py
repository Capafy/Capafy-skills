from __future__ import annotations

import json
from pathlib import Path

from packaging.ship.artifacts.archive import build_bundle_archive
from packaging._shared.common.fs import cleanup_staging_root
from packaging._shared.contracts.bundle_context import BUNDLE_CONTEXT_NAME
from packaging._shared.contracts.reviewed_scan import (
    load_reviewed_scan_payload,
    sanitize_reviewed_scan_payload,
    validate_reviewed_scan_gate,
)
from packaging._shared.contracts.stage_manifest import STAGE_MANIFEST_NAME, load_stage_manifest
from packaging._shared.reviewed_scan.dispose import reviewed_scan_has_final_dispositions


def _build_buyout_package_payload() -> dict:
    return {
        "agent_type": "download",
        "url_proxy": [],
        "generic": [],
        "env_var": [],
    }


def build_buyout_artifact_package_payload(
    *,
    effective_scan_payload: dict,
) -> dict:
    effective_scan_payload = sanitize_reviewed_scan_payload(effective_scan_payload)
    base = _build_buyout_package_payload()

    for key in ("url_proxy", "generic", "env_var"):
        items = effective_scan_payload.get(key)
        if isinstance(items, list) and items:
            base[key] = list(items)
    return base


def build_buyout_validate_reviewed_scan_json(
    *,
    effective_scan_payload: dict,
) -> str | None:
    return json.dumps(sanitize_reviewed_scan_payload(effective_scan_payload), ensure_ascii=False)


def package_buyout_staging(
    staging_root: Path,
    package_json: str,
    output_path: Path,
    *,
    cleanup_staging: bool = False,
) -> dict:
    package_payload = load_reviewed_scan_payload(package_json, label="package_json")
    validate_reviewed_scan_gate(package_payload, label="package_json")
    if not isinstance(package_payload, dict):
        raise ValueError("package_json must be an object")
    if not reviewed_scan_has_final_dispositions(package_payload):
        raise ValueError("buyout package requires reviewed_scan payload with final_disposition for every item")

    stage_manifest = load_stage_manifest(staging_root)
    exclude_prefixes = ("_scan_only",)

    manifest_prefixes = stage_manifest.get("scan_only_prefixes", [])
    if isinstance(manifest_prefixes, list):
        exclude_prefixes = tuple(
            dict.fromkeys(
                [
                    *exclude_prefixes,
                    *[str(item).strip().rstrip("/") for item in manifest_prefixes if str(item).strip()],
                ]
            )
        )
    bundle_result = build_bundle_archive(
        staging_root,
        output_path,
        exclude_paths={BUNDLE_CONTEXT_NAME, STAGE_MANIFEST_NAME},
        exclude_prefixes=exclude_prefixes,
    )
    payload = {
        "agent_type": "download",
        "bundle": bundle_result,
    }
    if cleanup_staging:
        payload["cleanup_summary"] = cleanup_staging_root(staging_root)
    return payload
