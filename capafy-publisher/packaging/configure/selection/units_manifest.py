from __future__ import annotations

import json
from pathlib import Path


def write_selected_units_manifest(
    staging_root: Path,
    *,
    selected_skill_paths: set[str] | None,
    selected_plugin_paths: set[str] | None,
    selected_cron_paths: set[str] | None,
    runtime_validation: dict | None = None,
) -> Path:
    payload = {
        "selected_skill_paths": sorted(set(selected_skill_paths or set())),
        "selected_plugin_paths": sorted(set(selected_plugin_paths or set())),
        "selected_cron_paths": sorted(set(selected_cron_paths or set())),
    }
    if runtime_validation is not None:
        payload["runtime_validation"] = runtime_validation
    path = staging_root / "agent.selected_units.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


__all__ = ["write_selected_units_manifest"]
