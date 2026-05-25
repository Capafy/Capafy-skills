from __future__ import annotations
from typing import Optional

from pathlib import Path

from packaging.configure.sensitive.placeholders import (
    build_redaction_placeholder_candidates,
    build_runtime_redaction_placeholder_candidates,
)
from packaging._shared.reviewed_scan.dispose import EXCLUDE_VALUE, REPLACE_WITH_PLACEHOLDER
from packaging.configure.sensitive.value_strip import strip_value_from_staging
from packaging.configure.sensitive.literals import looks_like_platform_managed_placeholder_value
from packaging.configure.staging.strip.targets import collect_strip_item_targets


def _run_strip_by_platform_groups(staging_root: Path, strip_targets: list[dict]) -> dict:
    touched_files: set[str] = set()
    items: list[dict] = []
    total_replacements = 0
    for target in strip_targets:
        if looks_like_platform_managed_placeholder_value(str(target.get("value", ""))):
            continue
        placeholder_candidates = list(target.get("placeholder_candidates", []))
        for item in target.get("items", []):
            if not isinstance(item, dict):
                continue

            for candidate in build_runtime_redaction_placeholder_candidates(item, staging_root):
                if candidate not in placeholder_candidates:
                    placeholder_candidates.append(candidate)
        result = strip_value_from_staging(
            staging_root,
            target["value"],
            target["placeholder"],
            extra_candidates=placeholder_candidates,
        )
        touched_files.update(result["replaced_in"])
        total_replacements += result["total_replacements"]
        items.append(
            {
                "placeholder": target["placeholder"],
                "placeholder_candidate_count": len(placeholder_candidates),
                "source_count": len(target["sources"]),
                "sources": target["sources"],
                "replaced_file_count": len(result["replaced_in"]),
                "total_replacements": result["total_replacements"],
            }
        )
    return {
        "item_count": len(strip_targets),
        "touched_file_count": len(touched_files),
        "total_replacements": total_replacements,
        "items": items,
    }


def _buyout_entry_strip_specs(entry: dict) -> list[tuple[str, str]]:
    specs: list[tuple[str, str]] = []
    api_key = entry.get("api_key")
    if isinstance(api_key, dict):
        value = str(api_key.get("value", "")).strip()
        placeholder = str(api_key.get("placeholder", "")).strip()
        if value:
            specs.append((value, placeholder))
    url = entry.get("url")
    if isinstance(url, dict):
        value = str(url.get("value", "")).strip()
        placeholder = str(url.get("placeholder", "")).strip()
        if value:
            specs.append((value, placeholder))
    if specs:
        return specs
    value = str(entry.get("value", "")).strip()
    placeholder = str(entry.get("placeholder", "")).strip()
    if value:
        specs.append((value, placeholder))
    return specs


def _run_strip_by_final_disposition(staging_root: Path, reviewed_scan: dict) -> dict:
    touched_files: set[str] = set()
    items: list[dict] = []
    total_replacements = 0
    for bucket in ("url_proxy", "generic", "env_var"):
        raw_items = reviewed_scan.get(bucket, [])
        if not isinstance(raw_items, list):
            continue
        for entry in raw_items:
            if not isinstance(entry, dict):
                continue
            disposition = str(entry.get("final_disposition", "")).strip()
            specs = _buyout_entry_strip_specs(entry)

            if disposition in {REPLACE_WITH_PLACEHOLDER, EXCLUDE_VALUE}:

                placeholder_override = "" if disposition == EXCLUDE_VALUE else None
                item_replacements = 0
                item_files: set[str] = set()
                for value, placeholder in specs:
                    result = strip_value_from_staging(
                        staging_root,
                        value,
                        placeholder_override if placeholder_override is not None else placeholder,
                        allow_empty_placeholder=placeholder_override is not None,
                    )
                    item_files.update(result["replaced_in"])
                    item_replacements += result["total_replacements"]
                touched_files.update(item_files)
                total_replacements += item_replacements
                items.append(
                    {
                        "bucket": bucket,
                        "disposition": disposition,
                        "replaced_file_count": len(item_files),
                        "total_replacements": item_replacements,
                    }
                )
                continue

            raise ValueError(f"unknown disposition: {disposition}")
    return {
        "item_count": len(items),
        "touched_file_count": len(touched_files),
        "deleted_file_count": 0,
        "total_replacements": total_replacements,
        "items": items,
    }


def run_strip_batch(
    staging_root: Path,
    strip_targets: Optional[list[dict]] = None,
    *,
    reviewed_scan: Optional[dict] = None,
    agent_type: str = "run_online",
) -> dict:
    if agent_type == "download":
        if not isinstance(reviewed_scan, dict):
            raise ValueError("download strip requires reviewed_scan payload")
        return _run_strip_by_final_disposition(staging_root, reviewed_scan)
    targets = collect_strip_item_targets(
        strip_targets or [],
        placeholder_candidates_for_item=build_redaction_placeholder_candidates,
    )
    return _run_strip_by_platform_groups(staging_root, targets)
