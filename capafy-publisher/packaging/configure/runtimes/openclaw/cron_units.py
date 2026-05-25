from __future__ import annotations
from typing import Optional

import json
from pathlib import Path

from packaging._shared.common.home import safe_expanduser_path
from packaging._shared.contracts.stage_plan import StagePlan
from packaging.configure.runtimes.openclaw.workspace_common import (
    OPENCLAW_CRON_FILE,
    OPENCLAW_CRON_UNIT_PREFIX,
    OPENCLAW_ROOT,
    OPENCLAW_SELECTED_CRON_IDS_METADATA_KEY,
    CRON_PATH_NAME_SANITIZE_PATTERN,
    CRON_PATH_SPACE_PATTERN,
)


def _cron_job_path_token(job_name: Optional[str], job_id: str) -> str:
    base = str(job_name or "").strip() or job_id
    sanitized = CRON_PATH_NAME_SANITIZE_PATTERN.sub("-", base)
    sanitized = CRON_PATH_SPACE_PATTERN.sub("-", sanitized).strip("-._ ")
    return sanitized or job_id


def build_openclaw_cron_unit_path(job_id: str, *, job_name: Optional[str] = None) -> str:
    normalized = str(job_id or "").strip()
    if not normalized:
        return ""
    token = _cron_job_path_token(job_name, normalized)
    if token == normalized:
        return f"{OPENCLAW_CRON_UNIT_PREFIX}{normalized}"
    return f"{OPENCLAW_CRON_UNIT_PREFIX}{token}#{normalized}"


def selected_openclaw_cron_ids(selected_paths: Optional[set[str]]) -> set[str]:
    if not selected_paths:
        return set()
    selected_ids: set[str] = set()
    for path in selected_paths:
        normalized = str(path or "").strip()
        job_id = ""
        if normalized.startswith(OPENCLAW_CRON_UNIT_PREFIX):
            suffix = normalized[len(OPENCLAW_CRON_UNIT_PREFIX) :].strip()
            if suffix.startswith("jobs.json#id:"):
                continue
            if suffix and "/" not in suffix:
                job_id = suffix.rsplit("#", 1)[-1].strip()
        if job_id:
            selected_ids.add(job_id)
    return selected_ids


def _openclaw_cron_file(openclaw_root: Path) -> Path:
    return safe_expanduser_path(openclaw_root / OPENCLAW_CRON_FILE)


def _load_openclaw_cron_payload(openclaw_root: Path) -> tuple[Path, Optional[dict]]:
    cron_path = _openclaw_cron_file(openclaw_root)
    if not cron_path.is_file():
        return cron_path, None
    try:
        payload = json.loads(cron_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return cron_path, None
    if not isinstance(payload, dict):
        return cron_path, None
    return cron_path, payload


def _cron_job_name(job: dict) -> str:
    name = str(job.get("name", "")).strip()
    if name:
        return name
    job_id = str(job.get("id", "")).strip()
    if job_id:
        return f"cron-{job_id[:8]}"
    return "cron-job"


def _cron_schedule_summary(job: dict) -> str:
    schedule = job.get("schedule")
    if isinstance(schedule, dict):
        kind = str(schedule.get("kind", "")).strip()
        expr = str(schedule.get("expr", "")).strip()
        tz = str(schedule.get("tz", "")).strip()
        parts = [part for part in (kind, expr, tz) if part]
        return " / ".join(parts)
    return str(schedule or "").strip()


def _cron_job_synopsis(job: dict) -> str:
    lines = [f"Cron job: {_cron_job_name(job)}"]
    schedule_summary = _cron_schedule_summary(job)
    if schedule_summary:
        lines.append(f"Schedule: {schedule_summary}")
    payload = job.get("payload")
    if isinstance(payload, dict):
        prompt = str(payload.get("prompt", "")).strip()
        if prompt:
            lines.append(prompt)
    return "\n".join(lines)


def _cron_schedule_payload(job: dict) -> dict[str, str]:
    schedule = job.get("schedule")
    if not isinstance(schedule, dict):
        return {}
    normalized: dict[str, str] = {}
    for key in ("kind", "expr", "tz"):
        value = str(schedule.get(key, "")).strip()
        if value:
            normalized[key] = value
    return normalized


def _cron_payload_payload(job: dict) -> dict[str, str]:
    payload = job.get("payload")
    if not isinstance(payload, dict):
        return {}
    prompt = str(payload.get("prompt", "")).strip()
    if not prompt:
        return {}
    return {"prompt": prompt}


def discover_openclaw_cron_units(
    *,
    openclaw_root: Path = OPENCLAW_ROOT,
) -> list[dict]:
    _, payload = _load_openclaw_cron_payload(openclaw_root)
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs, list):
        return []

    discovered: list[dict] = []
    seen_paths: set[str] = set()
    for job in jobs:
        if not isinstance(job, dict):
            continue
        job_id = str(job.get("id", "")).strip()
        name = _cron_job_name(job)
        unit_path = build_openclaw_cron_unit_path(job_id, job_name=name)
        if not unit_path or unit_path in seen_paths:
            continue
        synopsis = _cron_job_synopsis(job)
        reference_tokens = [token for token in (name, job_id) if token]
        discovered.append(
            {
                "path": unit_path,
                "id": job_id,
                "name": name,
                "schedule": _cron_schedule_payload(job),
                "payload": _cron_payload_payload(job),
                "source_root": ".openclaw/cron",
                "unit_type": "cron",
                "has_primary_doc": True,
                "has_skill_md": False,
                "file_count": 1,
                "size_bytes": len(json.dumps(job, ensure_ascii=False)),
                "synopsis": synopsis,
                "reference_tokens": reference_tokens,
                "suspicious_reasons": [],
            }
        )
        seen_paths.add(unit_path)
    return discovered


def _with_selected_cron_metadata(metadata: dict[str, object], selected_ids: set[str]) -> dict[str, object]:
    updated = dict(metadata)
    updated[OPENCLAW_SELECTED_CRON_IDS_METADATA_KEY] = json.dumps(sorted(selected_ids), ensure_ascii=False)
    return updated


def augment_stage_plan_with_selected_cron_jobs(
    stage_plan: StagePlan,
    *,
    selected_paths: Optional[set[str]],
    openclaw_root: Path = OPENCLAW_ROOT,
) -> StagePlan:
    selected_ids = selected_openclaw_cron_ids(selected_paths)
    if not selected_ids:
        return stage_plan

    cron_path = _openclaw_cron_file(openclaw_root)
    if not cron_path.is_file():
        return stage_plan

    return StagePlan(
        tree_sources=list(stage_plan.tree_sources),
        file_sources=list(stage_plan.file_sources),
        metadata=_with_selected_cron_metadata(dict(stage_plan.metadata), selected_ids),
    )


__all__ = [
    "OPENCLAW_CRON_UNIT_PREFIX",
    "build_openclaw_cron_unit_path",
    "augment_stage_plan_with_selected_cron_jobs",
    "discover_openclaw_cron_units",
    "selected_openclaw_cron_ids",
]
