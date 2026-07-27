from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from packaging._shared.contracts.bundle_context import validate_agent_type
from packaging._shared.contracts.reviewed_scan import normalize_reviewed_scan_payload
from packaging.runtimes import get_runtime_validation_target
from packaging.ship.artifacts.download_validation import validate_download_runtime


def _validate_run_online_runtime(
    runtime_root: Path,
    *,
    target,
    reviewed_scan_payload: object,
) -> dict:
    if not isinstance(reviewed_scan_payload, dict):
        raise ValueError("run_online validation requires reviewed_scan")
    normalize_reviewed_scan_payload(
        reviewed_scan_payload,
        label="reviewed_scan",
    )
    return target.validate_runtime(runtime_root)


def run_artifact_validate(
    *,
    staging_path: str,
    env_id: str,
    reviewed_scan: dict[str, Any],
    agent_type: str,
) -> dict[str, Any]:
    staging_root = Path(staging_path)
    if not staging_root.is_dir():
        raise ValueError(f"validation staging directory does not exist: {staging_root}")

    resolved_agent_type = validate_agent_type(agent_type)
    target, _ = get_runtime_validation_target(env_id)
    with tempfile.TemporaryDirectory(prefix="developer-runtime-validate-") as tmpdir:
        runtime_root = Path(tmpdir) / "runtime"
        shutil.copytree(staging_root, runtime_root, symlinks=True)
        if resolved_agent_type == "run_online":
            validation_payload = _validate_run_online_runtime(
                runtime_root,
                target=target,
                reviewed_scan_payload=reviewed_scan,
            )
        else:
            validation_payload = validate_download_runtime(
                runtime_root,
                reviewed_scan_payload=reviewed_scan,
            )

    return validation_payload


__all__ = ["run_artifact_validate"]
