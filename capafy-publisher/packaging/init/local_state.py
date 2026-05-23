from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from packaging._shared.common.constants import DEVELOPER_WORK_DIR_PATH
from packaging._shared.contracts.publish_work_state import (
    PUBLISH_WORK_STATE_KEEP_RELATIVE_PATHS,
    STAGE_INIT_COMPLETED,
    classify_publish_work_state_cleanup_error,
    write_publish_work_state_manifest,
)
from packaging.init.explicit_skill import explicit_skill_for_manifest


def _cleanup_publish_work_state_path(
    item: Path,
    *,
    work_dir: Path,
    removed: list[str],
    preserved: list[str],
) -> None:
    relpath = item.relative_to(work_dir)
    if relpath in PUBLISH_WORK_STATE_KEEP_RELATIVE_PATHS:
        preserved.append(relpath.as_posix())
        return

    try:
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
    except OSError as exc:
        error_kind = classify_publish_work_state_cleanup_error(exc)
        raise RuntimeError(
            f"failed to clean previous publish work state ({error_kind}): {item}: {exc}"
        ) from exc
    removed.append(relpath.as_posix())


def cleanup_previous_publish_work_state(work_dir: Path = DEVELOPER_WORK_DIR_PATH) -> dict[str, Any]:
    removed: list[str] = []
    preserved: list[str] = []
    if not work_dir.exists():
        return {"work_dir": str(work_dir), "removed": removed, "preserved": preserved}

    for item in sorted(work_dir.iterdir(), key=lambda path: path.name):
        _cleanup_publish_work_state_path(
            item,
            work_dir=work_dir,
            removed=removed,
            preserved=preserved,
        )
    return {"work_dir": str(work_dir), "removed": removed, "preserved": preserved}


def write_init_completed_manifest(payload: dict[str, Any], *, work_dir: Path = DEVELOPER_WORK_DIR_PATH) -> None:
    extra = {"runtime_dir": str(payload.get("runtime_dir", "") or "").strip()}
    explicit_skill = explicit_skill_for_manifest(payload.get("explicit_skill"))
    if explicit_skill:
        extra["explicit_skill"] = explicit_skill
    external_skill_bindings = payload.get("external_skill_bindings")
    if isinstance(external_skill_bindings, list) and external_skill_bindings:
        extra["external_skill_bindings"] = external_skill_bindings
    write_publish_work_state_manifest(
        work_dir,
        agent_id=str(payload.get("agent_id", "")).strip(),
        agent_version_id=str(payload.get("agent_version_id", "")).strip(),
        env_id=str(payload.get("env_id", "")).strip(),
        agent_type="",
        stage=STAGE_INIT_COMPLETED,
        review_url=str(payload.get("review_url", "")).strip() or None,
        extra=extra,
    )


__all__ = [
    "cleanup_previous_publish_work_state",
    "write_init_completed_manifest",
]
