from __future__ import annotations

import json
from pathlib import Path



STAGE_MANIFEST_NAME = "agent.stage_manifest.internal.json"


def write_stage_manifest(
    staging_root: Path,
    *,
    scan_only_prefixes: tuple[str, ...],
    scan_only_source_map: dict[str, str],
    staging_digest: str,
    scan_only_digest: str,
    generated_at: str,
    excluded_credential_files: tuple[str, ...] = (),
) -> Path:
    payload = {
        "schema_version": 1,
        "scan_only_prefixes": list(scan_only_prefixes),
        "scan_only_source_map": dict(scan_only_source_map),
        "staging_digest": staging_digest,
        "scan_only_digest": scan_only_digest,
        "generated_at": generated_at,
    }
    if excluded_credential_files:
        payload["excluded_credential_files"] = list(excluded_credential_files)
    output_path = staging_root / STAGE_MANIFEST_NAME
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def load_stage_manifest(staging_root: Path) -> dict:
    manifest_path = staging_root / STAGE_MANIFEST_NAME
    if not manifest_path.is_file():
        raise ValueError(f"{STAGE_MANIFEST_NAME} is missing")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{STAGE_MANIFEST_NAME} parse failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{STAGE_MANIFEST_NAME} top-level value must be an object")
    return payload


__all__ = [
    "STAGE_MANIFEST_NAME",
    "load_stage_manifest",
    "write_stage_manifest",
]
