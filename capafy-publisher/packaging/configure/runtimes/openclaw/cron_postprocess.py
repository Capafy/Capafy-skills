from __future__ import annotations

import json
from pathlib import Path

from packaging._shared.common.constants import PLACEHOLDER
from packaging._shared.contracts.stage_plan import StagePlan
from packaging.configure.runtimes.openclaw.workspace_common import (
    OPENCLAW_CRON_DISPLAY_PATH,
    OPENCLAW_SELECTED_CRON_IDS_METADATA_KEY,
    DELIVERY_SAFE_CONTAINER_KEYS,
    DELIVERY_SAFE_SCALAR_KEYS,
)
from packaging.configure.sensitive.keywords import (
    contains_explicit_secret_keyword,
    contains_explicit_value_keyword,
)


def _clean_delivery_value(key_name: str, value: object) -> tuple[object, int]:
    if key_name in {"mode", "channel", "format", "template"}:
        return value, 0

    if isinstance(value, dict):
        cleaned = 0
        updated = dict(value)
        for child_key, child_value in value.items():
            new_value, count = _clean_delivery_value(str(child_key), child_value)
            if count:
                updated[child_key] = new_value
                cleaned += count
        if cleaned:
            return updated, cleaned
        if contains_explicit_secret_keyword(key_name) or contains_explicit_value_keyword(key_name):
            return PLACEHOLDER, (0 if value == PLACEHOLDER else 1)
        return value, 0

    if isinstance(value, list):
        if contains_explicit_secret_keyword(key_name) or contains_explicit_value_keyword(key_name):
            cleaned = 0
            updated_items: list[object] = []
            for item in value:
                if item == PLACEHOLDER:
                    updated_items.append(item)
                    continue
                updated_items.append(PLACEHOLDER)
                cleaned += 1
            return updated_items, cleaned
        cleaned = 0
        updated_items = []
        for item in value:
            if isinstance(item, dict):
                new_item, count = _clean_delivery_value(key_name, item)
                updated_items.append(new_item)
                cleaned += count
            else:
                updated_items.append(item)
        if cleaned:
            return updated_items, cleaned
        return value, 0

    if contains_explicit_secret_keyword(key_name) or contains_explicit_value_keyword(key_name):
        return PLACEHOLDER, (0 if value == PLACEHOLDER else 1)
    return value, 0


def _clean_delivery_payload(delivery: dict) -> tuple[dict, int]:
    cleaned = 0
    updated_delivery = dict(delivery)
    for key, value in delivery.items():
        normalized_key = str(key)
        if normalized_key in DELIVERY_SAFE_SCALAR_KEYS | DELIVERY_SAFE_CONTAINER_KEYS:
            new_value, count = _clean_delivery_value(normalized_key, value)
            if count:
                updated_delivery[key] = new_value
                cleaned += count
            continue
        if value != PLACEHOLDER:
            updated_delivery[key] = PLACEHOLDER
            cleaned += 1
    return updated_delivery, cleaned


def clean_cron_jobs(staging_root: Path) -> int:
    cron_path = staging_root / ".openclaw" / "cron" / "jobs.json"
    if not cron_path.is_file():
        return 0

    try:
        payload = json.loads(cron_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0

    if not isinstance(payload, dict):
        return 0

    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        return 0

    cleaned = 0
    for job in jobs:
        if not isinstance(job, dict):
            continue
        for state_key in ("state", "lastRunAtMs", "lastStatus", "consecutiveErrors", "runCount"):
            if state_key in job:
                del job[state_key]
                cleaned += 1
        for secret_key in ("env", "secrets", "credentials", "variables"):
            if secret_key in job:
                del job[secret_key]
                cleaned += 1
        delivery = job.get("delivery")
        if isinstance(delivery, dict):
            updated_delivery, delivery_cleaned = _clean_delivery_payload(delivery)
            if delivery_cleaned:
                cleaned += delivery_cleaned
            job["delivery"] = updated_delivery

    if cleaned:
        cron_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cleaned


def filter_selected_cron_jobs(staging_root: Path, stage_plan: StagePlan) -> int:
    selected_ids_json = str(stage_plan.metadata.get(OPENCLAW_SELECTED_CRON_IDS_METADATA_KEY, "")).strip()
    if not selected_ids_json:
        return 0
    try:
        selected_ids = {
            str(item).strip()
            for item in json.loads(selected_ids_json)
            if str(item).strip()
        }
    except json.JSONDecodeError:
        return 0
    if not selected_ids:
        return 0

    cron_path = staging_root / OPENCLAW_CRON_DISPLAY_PATH
    if not cron_path.is_file():
        return 0
    try:
        payload = json.loads(cron_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0
    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        return 0

    filtered_jobs = [
        job
        for job in jobs
        if isinstance(job, dict) and str(job.get("id", "")).strip() in selected_ids
    ]
    removed = len(jobs) - len(filtered_jobs)
    if removed <= 0:
        return 0
    payload["jobs"] = filtered_jobs
    cron_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return removed


__all__ = ["clean_cron_jobs", "filter_selected_cron_jobs"]
