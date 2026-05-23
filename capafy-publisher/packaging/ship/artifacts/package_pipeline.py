from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packaging._shared.contracts.bundle_context import validate_agent_type
from packaging._shared.contracts.reviewed_scan import load_reviewed_scan_payload as load_reviewed_scan_contract_payload
from packaging.ship.contexts import ArtifactPackageContext, PackageContext
from packaging.ship.mode_dispatch import get_ship_mode


def _agent_type_from_package_json(package_json: str) -> str:
    payload = load_reviewed_scan_contract_payload(package_json, label="package_json")
    if not isinstance(payload, dict):
        raise ValueError("package_json must be an object")
    agent_type = str(payload.get("agent_type", "")).strip()
    if not agent_type:
        raise ValueError("package_json is missing top-level agent_type")
    return validate_agent_type(agent_type)


def run_package_pipeline(
    staging_root: Path,
    package_json: str,
    output_path: Path,
    *,
    cleanup_staging: bool = False,
) -> dict:
    agent_type = _agent_type_from_package_json(package_json)
    mode = get_ship_mode(agent_type)
    return mode.package(
        PackageContext(
            staging_root=staging_root,
            package_json=package_json,
            output_path=output_path,
            cleanup_staging=cleanup_staging,
        )
    )


def run_artifact_package(
    *,
    staging_root: str,
    reviewed_scan: dict[str, Any],
    bundle_path: str,
    agent_type: str,
) -> dict[str, Any]:
    staging = Path(staging_root)
    resolved_agent_type = validate_agent_type(agent_type)
    mode = get_ship_mode(resolved_agent_type)
    package_payload = mode.artifact_package_payload(ArtifactPackageContext(effective_scan_payload=reviewed_scan))
    return run_package_pipeline(
        staging,
        json.dumps(package_payload, ensure_ascii=False),
        Path(bundle_path),
    )


__all__ = [
    "run_artifact_package",
    "run_package_pipeline",
]
