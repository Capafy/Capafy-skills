from __future__ import annotations

from pathlib import Path

from packaging._shared.common.exclusion_rules import default_exclude_use, exclude_reason_code_for_path


def build_exclude_entry(
    relpath: str,
    *,
    reason: str = "",
    added_by: str = "scan",
) -> dict[str, str] | None:
    normalized = str(relpath or "").strip().rstrip("/")
    if not normalized:
        return None
    reason_code = exclude_reason_code_for_path(normalized, reason=reason)
    if not reason_code:
        return None
    return {
        "source": normalized,
        "reason": reason_code,
        "use": default_exclude_use(normalized, reason_code=reason_code),
        "added_by": str(added_by or "").strip() or "scan",
    }


def project_scan_excludes(
    staging_path: Path,
    scan_excludes: list[dict],
) -> list[dict]:
    from packaging._shared.contracts.stage_manifest import load_stage_manifest

    excludes: list[dict] = []
    seen_sources: set[str] = set()

    def append_exclude(entry: dict | None) -> None:
        if not isinstance(entry, dict):
            return
        source = str(entry.get("source", "")).strip()
        if not source or source in seen_sources:
            return
        excludes.append(entry)
        seen_sources.add(source)

    manifest = load_stage_manifest(staging_path)
    manifest_excluded_files = manifest.get("excluded_credential_files", [])
    if isinstance(manifest_excluded_files, list):
        for item in manifest_excluded_files:
            append_exclude(build_exclude_entry(str(item or "").strip(), added_by="scan"))

    for item in scan_excludes:
        append_exclude(item if isinstance(item, dict) else None)

    return excludes


__all__ = [
    "build_exclude_entry",
    "project_scan_excludes",
]
