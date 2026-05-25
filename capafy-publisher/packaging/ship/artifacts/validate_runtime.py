from __future__ import annotations

from datetime import datetime
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Optional

from packaging._shared.common.constants import DEFAULT_BUNDLE_PATH, DEFAULT_STAGING_PATH
from packaging._shared.common.fs import normalize_path
from packaging._shared.contracts.bundle_context import looks_like_buyout_package
from packaging.ship.contexts import ArtifactValidateContext, ValidateContext
from packaging.ship.mode_dispatch import get_ship_mode
from packaging.runtimes import get_runtime_validation_target


SERIAL_VALIDATE_RUNTIME_HINT = "The previous step is incomplete. Run stage -> package -> validate-runtime in order."

VALIDATE_RUNTIME_MTIME_TOLERANCE_SECONDS = 2.0
VALIDATE_RUNTIME_MTIME_TOLERANCE_ENV = "CAPAFY_VALIDATE_RUNTIME_MTIME_TOLERANCE_SECONDS"


def detect_agent_type_from_runtime(runtime_root: Path) -> str:
    if looks_like_buyout_package(runtime_root):
        return "download"
    return "run_online"


def _safe_extract_zip(archive_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive_path, "r") as archive:
        resolved_destination = destination.resolve()
        for member in archive.infolist():
            if (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError(f"bundle contains unsupported symlink entry: {member.filename}")
            member_path = destination / member.filename
            resolved_member = member_path.resolve()
            if resolved_member != resolved_destination and resolved_destination not in resolved_member.parents:
                raise ValueError(f"bundle contains a path that escapes the destination: {member.filename}")
        archive.extractall(destination)


def _materialize_validate_input(
    input_path: Path,
    destination: Path,
) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if input_path.is_dir():
        shutil.copytree(input_path, destination, symlinks=True)
        return "staging"
    destination.mkdir(parents=True, exist_ok=True)
    if input_path.is_file() and zipfile.is_zipfile(input_path):
        _safe_extract_zip(input_path, destination)
        return "bundle"
    raise ValueError(f"validate-runtime only supports a staging directory or bundle zip archive: {input_path}")


def _run_validate_runtime_pipeline(
    input_path: Path,
    *,
    target_name: Optional[str] = None,
    expected_version: Optional[str] = None,
    reviewed_scan_json: Optional[str] = None,
    reviewed_scan_file: Optional[str] = None,
    staging_root: Optional[Path] = None,
) -> tuple[int, dict]:
    ensure_validate_runtime_input_ready(input_path, staging_root=staging_root)
    target, resolved_target_name = get_runtime_validation_target(target_name)

    with tempfile.TemporaryDirectory(prefix="developer-runtime-validate-") as tmpdir:
        materialized_root = Path(tmpdir) / "runtime"
        input_kind = _materialize_validate_input(
            input_path,
            materialized_root,
        )
        runtime_root = materialized_root
        agent_type = detect_agent_type_from_runtime(runtime_root) or "run_online"
        mode = get_ship_mode(agent_type)
        validate_context = {
            "runtime_root": runtime_root,
            "reviewed_scan_json": reviewed_scan_json,
            "reviewed_scan_file": reviewed_scan_file,
        }
        if agent_type == "run_online":
            validate_context.update(
                {
                    "target": target,
                    "expected_version": expected_version,
                }
            )
        else:
            validate_context["resolved_target_name"] = resolved_target_name
        validation_payload = mode.validate(ValidateContext(**validate_context))

    payload = {
        "target": resolved_target_name,
        "agent_type": agent_type,
        "input_path": str(input_path),
        "input_kind": input_kind,
        "expected_version": expected_version or "",
        **validation_payload,
    }
    return 0 if validation_payload.get("ok") else 1, payload


def run_validate_runtime_pipeline(
    input_path: Path,
    *,
    target_name: Optional[str] = None,
    expected_version: Optional[str] = None,
    reviewed_scan_json: Optional[str] = None,
    reviewed_scan_file: Optional[str] = None,
    staging_root: Optional[Path] = None,
) -> tuple[int, dict]:
    return _run_validate_runtime_pipeline(
        input_path,
        target_name=target_name,
        expected_version=expected_version,
        reviewed_scan_json=reviewed_scan_json,
        reviewed_scan_file=reviewed_scan_file,
        staging_root=staging_root,
    )


def _format_validate_guard_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).isoformat(timespec="seconds")


def latest_mtime_under(path: Path) -> float:
    latest_mtime = path.stat().st_mtime
    if not path.is_dir():
        return latest_mtime
    for child in path.rglob("*"):
        try:
            child_mtime = child.stat().st_mtime
        except OSError:
            continue
        if child_mtime > latest_mtime:
            latest_mtime = child_mtime
    return latest_mtime


def _default_staging_root_for_validate_input(input_path: Path) -> Optional[Path]:
    default_bundle_path = normalize_path(DEFAULT_BUNDLE_PATH)
    if input_path != default_bundle_path:
        return None
    default_staging_path = normalize_path(DEFAULT_STAGING_PATH)
    if not default_staging_path.is_dir():
        return None
    return default_staging_path


def _validate_runtime_mtime_tolerance_seconds() -> float:
    raw_value = str(os.environ.get(VALIDATE_RUNTIME_MTIME_TOLERANCE_ENV, "")).strip()
    if not raw_value:
        return VALIDATE_RUNTIME_MTIME_TOLERANCE_SECONDS
    try:
        tolerance = float(raw_value)
    except ValueError as exc:
        raise ValueError(
            f"{VALIDATE_RUNTIME_MTIME_TOLERANCE_ENV} must be a non-negative number of seconds"
        ) from exc
    if tolerance < 0:
        raise ValueError(
            f"{VALIDATE_RUNTIME_MTIME_TOLERANCE_ENV} must be a non-negative number of seconds"
        )
    return tolerance


def ensure_validate_runtime_input_ready(
    input_path: Path,
    *,
    staging_root: Optional[Path] = None,
) -> None:
    if not input_path.exists():
        raise ValueError(f"{SERIAL_VALIDATE_RUNTIME_HINT} Input path does not exist: {input_path}")
    if input_path.is_dir():
        return
    candidate_staging_root = staging_root or _default_staging_root_for_validate_input(input_path)
    if candidate_staging_root is None or not candidate_staging_root.is_dir():
        return
    bundle_mtime = input_path.stat().st_mtime
    staging_mtime = latest_mtime_under(candidate_staging_root)
    tolerance_seconds = _validate_runtime_mtime_tolerance_seconds()
    if staging_mtime - bundle_mtime <= tolerance_seconds:
        return
    raise ValueError(
        f"{SERIAL_VALIDATE_RUNTIME_HINT} Staging was updated at "
        f"{_format_validate_guard_timestamp(staging_mtime)}, which is later than bundle "
        f"{_format_validate_guard_timestamp(bundle_mtime)} "
        f"(staging={candidate_staging_root}, bundle={input_path}, tolerance_seconds={tolerance_seconds})"
    )


def run_artifact_validate(
    *,
    staging_path: str,
    env_id: str,
    reviewed_scan: dict[str, Any],
    agent_type: str,
) -> tuple[int, dict[str, Any]]:
    mode = get_ship_mode(agent_type)
    staging_root = Path(staging_path)
    return run_validate_runtime_pipeline(
        staging_root,
        target_name=env_id,
        expected_version=None,
        reviewed_scan_json=mode.artifact_validate_reviewed_scan_json(
            ArtifactValidateContext(effective_scan_payload=reviewed_scan)
        ),
        staging_root=staging_root,
    )


__all__ = [
    "SERIAL_VALIDATE_RUNTIME_HINT",
    "VALIDATE_RUNTIME_MTIME_TOLERANCE_ENV",
    "detect_agent_type_from_runtime",
    "ensure_validate_runtime_input_ready",
    "latest_mtime_under",
    "run_artifact_validate",
    "run_validate_runtime_pipeline",
]
