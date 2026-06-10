from __future__ import annotations

from pathlib import Path
from typing import Any, Union

from packaging._shared.common.cli import emit_json_result
from packaging._shared.common.constants import (
    DEFAULT_BUNDLE_PATH,
    DEFAULT_STAGING_PATH,
    DEVELOPER_WORK_DIR_PATH,
)
from packaging._shared.contracts.publish_work_state import (
    PublishWorkStateManifestError,
    require_publish_work_state_manifest,
    summarize_publish_work_state,
)


def _build_publish_local_files_summary(
    *,
    work_dir: Path = DEVELOPER_WORK_DIR_PATH,
    staging_path: Union[str, Path] = DEFAULT_STAGING_PATH,
    bundle_path: Union[str, Path] = DEFAULT_BUNDLE_PATH,
) -> dict[str, Any]:
    temp_state = summarize_publish_work_state(work_dir)
    return {
        "staging_exists": Path(staging_path).is_dir(),
        "bundle_exists": Path(bundle_path).is_file(),
        "reviewed_scan_exists": (work_dir / "reviewed-scan.json").is_file(),
        "confirmed_selections_exists": (work_dir / "confirmed-selections.json").is_file(),
        "last_good_selections_exists": (work_dir / "last-good-selections.json").is_file(),
        "existing": list(temp_state.get("existing", [])),
        "blocking": list(temp_state.get("blocking", [])),
        "preserved": list(temp_state.get("preserved", [])),
    }


def _local_only_status_fields(agent_id: str = "") -> dict[str, Any]:
    normalized_agent_id = str(agent_id or "").strip()
    command_agent_id = normalized_agent_id or "<agent_id>"
    return {
        "status_scope": "local_only",
        "does_not_include_remote_review_status": True,
        "remote_status_command": f"publish-remote-status --agent-id {command_agent_id}",
    }


def run_publish_status(
    *,
    developer_work_dir_path: Path = DEVELOPER_WORK_DIR_PATH,
    staging_path: Union[str, Path] = DEFAULT_STAGING_PATH,
    bundle_path: Union[str, Path] = DEFAULT_BUNDLE_PATH,
) -> tuple[dict[str, Any], int]:
    try:
        payload = require_publish_work_state_manifest(developer_work_dir_path)
    except PublishWorkStateManifestError as exc:
        return {
            **_local_only_status_fields(),
            "ok": False,
            "status": "error",
            "error": str(exc),
            "failed_step": "load_publish_work_state_manifest",
            "blocking_category": "invalid_publish_work_state_manifest",
            "local_files": _build_publish_local_files_summary(
                work_dir=developer_work_dir_path,
                staging_path=staging_path,
                bundle_path=bundle_path,
            ),
            "next_step": "fix_or_remove_invalid_publish_work_state_manifest",
        }, 1

    local_files = _build_publish_local_files_summary(
        work_dir=developer_work_dir_path,
        staging_path=staging_path,
        bundle_path=bundle_path,
    )
    if payload is None:
        return {
            **_local_only_status_fields(),
            "ok": True,
            "status": "no_active_publish",
            "next_step": "run_init_to_start_new_publish",
            "local_files": local_files,
        }, 0

    manifest_payload = dict(payload)
    manifest_payload.setdefault("ok", True)
    manifest_payload.update(_local_only_status_fields(str(manifest_payload.get("agent_id", "")).strip()))
    manifest_payload["local_files"] = local_files
    return manifest_payload, 0


def publish_status() -> int:
    payload, code = run_publish_status(developer_work_dir_path=DEVELOPER_WORK_DIR_PATH)
    return emit_json_result(payload, code)


__all__ = [
    "publish_status",
    "run_publish_status",
]
