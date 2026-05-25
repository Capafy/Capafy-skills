from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
import json
import os
import stat
import uuid
from datetime import datetime, timezone
import errno
from pathlib import Path
from typing import Any, Dict, List, Optional

from packaging._shared.common.fs import safe_chmod


PUBLISH_WORK_STATE_MANIFEST_NAME = "publish-work-state.json"

STAGE_INIT_COMPLETED = "init_completed"
STAGE_BUNDLE_PREPARED = "bundle_prepared"
STAGE_CONFIG_SUBMITTED = "config_submitted"
STAGE_SHIPPED = "shipped"
VALID_PUBLISH_WORK_STATE_STAGES = (
    STAGE_INIT_COMPLETED,
    STAGE_BUNDLE_PREPARED,
    STAGE_CONFIG_SUBMITTED,
    STAGE_SHIPPED,
)


class PublishWorkStateManifestError(ValueError):
    pass


@dataclass(frozen=True)
class PublishWorkState:

    agent_id: str
    agent_version_id: str
    env_id: str
    current_stage: str
    agent_type: str = ""
    pending_review_url: Optional[str] = None
    last_updated: str = ""
    history: Optional[List[Dict[str, Any]]] = None
    extra: Optional[Dict[str, Any]] = None
    schema_version: int = 1

    @property
    def staging_path(self) -> str:
        return self.extra_value("staging_path")

    @property
    def reviewed_scan_path(self) -> str:
        return self.extra_value("reviewed_scan_path")

    @property
    def runtime_dir(self) -> str:
        return self.extra_value("runtime_dir")

    def extra_value(self, key: str, default: str = "") -> str:
        extra = self.extra if isinstance(self.extra, dict) else {}
        return str(extra.get(key, default)).strip()

    def with_stage(self, stage: str, *, extra: Optional[Optional[Dict[str, Any]]] = None) -> PublishWorkState:
        updates: dict[str, Any] = {"current_stage": _require_valid_stage(stage)}
        if extra is not None:
            updates["extra"] = extra
        return replace(self, **updates)


def publish_work_state_manifest_path(work_dir: Path) -> Path:
    return work_dir / PUBLISH_WORK_STATE_MANIFEST_NAME


def require_publish_work_state_manifest(work_dir: Path) -> Optional[dict[str, Any]]:
    path = publish_work_state_manifest_path(work_dir)
    try:
        path_stat = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise PublishWorkStateManifestError(f"failed to inspect publish work-state manifest: {path}") from exc
    if not stat.S_ISREG(path_stat.st_mode):
        raise PublishWorkStateManifestError(f"publish work-state manifest path must be a regular file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PublishWorkStateManifestError(f"failed to parse publish work-state manifest: {path}") from exc
    except OSError as exc:
        raise PublishWorkStateManifestError(f"failed to read publish work-state manifest: {path}") from exc
    if not isinstance(payload, dict):
        raise PublishWorkStateManifestError(
            f"publish work-state manifest top-level value must be an object: {path}"
        )
    return payload


def _publish_work_state_from_manifest(manifest: dict[str, Any]) -> PublishWorkState:
    if not isinstance(manifest, dict):
        raise PublishWorkStateManifestError("publish work-state manifest must be an object")
    extra = manifest.get("extra")
    history = manifest.get("history")
    schema_version = manifest.get("schema_version", 1)
    try:
        normalized_schema_version = int(schema_version)
    except (TypeError, ValueError):
        normalized_schema_version = 1
    return PublishWorkState(
        schema_version=normalized_schema_version,
        agent_id=str(manifest.get("agent_id", "")).strip(),
        agent_version_id=str(manifest.get("agent_version_id", "")).strip(),
        env_id=str(manifest.get("env_id", "")).strip(),
        agent_type=str(manifest.get("agent_type", "")).strip(),
        current_stage=str(manifest.get("current_stage", "")).strip(),
        pending_review_url=(
            str(manifest.get("pending_review_url", "")).strip()
            if manifest.get("pending_review_url") is not None
            else None
        ),
        last_updated=str(manifest.get("last_updated", "")).strip(),
        history=_normalize_history(history),
        extra=dict(extra) if isinstance(extra, dict) else {},
    )


def require_publish_work_state(work_dir: Path) -> Optional[PublishWorkState]:
    manifest = require_publish_work_state_manifest(work_dir)
    return _publish_work_state_from_manifest(manifest) if isinstance(manifest, dict) else None


def write_publish_work_state_manifest(
    work_dir: Path,
    *,
    agent_id: Any,
    agent_version_id: Any,
    env_id: Any,
    agent_type: Any,
    stage: Any,
    review_url: Any = None,
    extra: Any = None,
) -> Path:
    normalized_agent_id = _require_non_empty_value("agent_id", agent_id)
    normalized_agent_version_id = _require_non_empty_value("agent_version_id", agent_version_id)
    normalized_env_id = _require_non_empty_value("env_id", env_id)
    stage_value = _require_valid_stage(stage)
    if stage_value == STAGE_INIT_COMPLETED:

        normalized_agent_type = agent_type.strip() if isinstance(agent_type, str) else ""
    else:
        normalized_agent_type = _require_non_empty_value("agent_type", agent_type)

    path = publish_work_state_manifest_path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    safe_chmod(work_dir, 0o700)
    temp_path = _publish_work_state_temp_path(work_dir)

    now = _utc_now()
    existing_payload = require_publish_work_state_manifest(work_dir) or {}
    history = _normalize_history(existing_payload.get("history"))
    if not history or history[-1].get("stage") != stage_value:
        history.append(
            {
                "stage": stage_value,
                "updated_at": now,
            }
        )

    payload = {
        "schema_version": 1,
        "agent_id": normalized_agent_id,
        "agent_version_id": normalized_agent_version_id,
        "env_id": normalized_env_id,
        "current_stage": stage_value,
        "pending_review_url": None if review_url is None else str(review_url),
        "last_updated": now,
        "history": history,
        "extra": extra if isinstance(extra, dict) else {},
    }
    if normalized_agent_type:
        payload["agent_type"] = normalized_agent_type
    raw_payload = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    try:
        with temp_path.open("w", encoding="utf-8") as handle:
            handle.write(raw_payload)
            handle.flush()
            os.fsync(handle.fileno())
        safe_chmod(temp_path, 0o600)
        os.replace(temp_path, path)
        _fsync_directory(work_dir)
    except Exception:
        _cleanup_temp_manifest_path(temp_path)
        raise
    return path



def _normalize_history(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        stage = str(item.get("stage", "")).strip()
        updated_at = str(item.get("updated_at", "")).strip()
        if not stage or not updated_at:
            continue
        normalized.append(
            {
                "stage": stage,
                "updated_at": updated_at,
            }
        )
    return normalized


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_non_empty_value(label: str, value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} must not be empty")
    return normalized


def _require_valid_stage(stage: Any) -> str:
    if not isinstance(stage, str):
        raise ValueError("stage must be a string")
    normalized = stage.strip()
    if normalized not in VALID_PUBLISH_WORK_STATE_STAGES:
        raise ValueError(f"stage must be one of {VALID_PUBLISH_WORK_STATE_STAGES}")
    return normalized


def _fsync_directory(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _publish_work_state_temp_path(work_dir: Path) -> Path:
    suffix = uuid.uuid4().hex
    return work_dir / f".{PUBLISH_WORK_STATE_MANIFEST_NAME}.{os.getpid()}.{suffix}.tmp"


def _cleanup_temp_manifest_path(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


PUBLISH_WORK_STATE_KEEP_RELATIVE_PATHS = {
    Path("self-update-state.json"),
    Path(PUBLISH_WORK_STATE_MANIFEST_NAME),
}

PUBLISH_WORK_STATE_BLOCKING_RELATIVE_PATHS = {
    Path("staging"),
    Path("bundle.zip"),
    Path("reviewed-scan.json"),
}
PUBLISH_SHIP_SUCCESS_CLEANUP_RELATIVE_PATHS = (
    Path("platform-requests"),
    Path("reviewed-scan.json"),
)


def _is_publish_work_state_path_or_child(relpath: Path, candidates: set[Path]) -> bool:
    return any(relpath == candidate or candidate in relpath.parents for candidate in candidates)


def _has_publish_work_state_descendants(relpath: Path, candidates: set[Path]) -> bool:
    return any(relpath in candidate.parents for candidate in candidates)


def summarize_publish_work_state(work_dir: Path) -> dict[str, Any]:
    existing: list[str] = []
    blocking: list[str] = []
    preserved: list[str] = []
    if not work_dir.exists():
        return {
            "work_dir": str(work_dir),
            "existing": existing,
            "blocking": blocking,
            "preserved": preserved,
        }

    for item in sorted(work_dir.iterdir(), key=lambda path: path.name):
        relpath = item.relative_to(work_dir)
        if _is_publish_work_state_path_or_child(relpath, PUBLISH_WORK_STATE_KEEP_RELATIVE_PATHS):
            preserved.append(relpath.as_posix())
            continue
        if _has_publish_work_state_descendants(relpath, PUBLISH_WORK_STATE_KEEP_RELATIVE_PATHS):
            preserved.append(relpath.as_posix())
            continue
        existing.append(relpath.as_posix())
        if _is_publish_work_state_path_or_child(relpath, PUBLISH_WORK_STATE_BLOCKING_RELATIVE_PATHS):
            blocking.append(relpath.as_posix())
    return {
        "work_dir": str(work_dir),
        "existing": existing,
        "blocking": blocking,
        "preserved": preserved,
    }


def cleanup_summary_from_existing_publish_work_state(existing_state: dict[str, Any]) -> dict[str, Any]:
    return {
        "work_dir": existing_state.get("work_dir"),
        "removed": [],
        "preserved": list(existing_state.get("preserved", [])),
        "blocked": list(existing_state.get("blocking", [])),
        "existing": list(existing_state.get("existing", [])),
    }


def cleanup_shipped_publish_intermediates(work_dir: Path) -> dict[str, Any]:
    removed: list[str] = []
    errors: list[dict[str, str]] = []
    work_dir_path = Path(work_dir)
    for relpath in PUBLISH_SHIP_SUCCESS_CLEANUP_RELATIVE_PATHS:
        path = work_dir_path / relpath
        if not path.exists():
            continue
        try:
            if path.is_dir() and not path.is_symlink():
                _remove_tree(path)
            else:
                path.unlink()
        except OSError as exc:
            errors.append(
                {
                    "path": relpath.as_posix(),
                    "error": str(exc),
                    "error_kind": classify_publish_work_state_cleanup_error(exc),
                }
            )
        else:
            removed.append(relpath.as_posix())
    summary: dict[str, Any] = {
        "publish_intermediates_removed": removed,
    }
    if errors:
        summary["publish_intermediates_errors"] = errors
    return summary


def _remove_tree(path: Path) -> None:
    for child in path.iterdir():
        if child.is_dir() and not child.is_symlink():
            _remove_tree(child)
        else:
            child.unlink()
    path.rmdir()


def classify_publish_work_state_cleanup_error(exc: OSError) -> str:
    if isinstance(exc, PermissionError):
        return "permission_denied"
    if isinstance(exc, FileNotFoundError):
        return "path_missing"
    if isinstance(exc, FileExistsError):
        return "path_conflict"
    if getattr(exc, "errno", None) == errno.ENOSPC:
        return "disk_full"
    return "os_error"
