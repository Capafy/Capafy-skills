from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, TypedDict

from packaging.publish.artifacts.path_refs import public_source_path_item


BUNDLE_CONTEXT_NAME = "agent.bundle_context.json"
VALID_AGENT_TYPES = frozenset({"run_online", "download"})
BUYOUT_FORBIDDEN_DIRS = {
    ".agents",
    ".claude",
    ".codex",
    ".config",
    ".openclaw",
    "skills",
    "workspace",
}
BUYOUT_FORBIDDEN_FILES = {
    "agent.runtime_dependencies.json",
}


class BundleContext(TypedDict, total=False):
    selection_groups: dict


def validate_agent_type(agent_type: Optional[str]) -> str:
    normalized = str(agent_type or "").strip()
    if not normalized:
        raise ValueError("agent_type must not be empty")
    if normalized not in VALID_AGENT_TYPES:
        raise ValueError(f"unknown agent_type: {normalized}")
    return normalized


def _public_selection_groups(selection_groups: dict) -> dict:
    public_groups: dict[str, Any] = dict(selection_groups)
    for key, value in selection_groups.items():
        if isinstance(value, list):
            public_groups[key] = [public_source_path_item(item) for item in value]
    return public_groups


def write_bundle_context(staging_root: Path, payload: dict) -> Path:
    output_path = staging_root / BUNDLE_CONTEXT_NAME
    public_payload: BundleContext = {}
    if "selection_groups" in payload:
        selection_groups = payload.get("selection_groups")
        if not isinstance(selection_groups, dict):
            raise ValueError("selection_groups must be an object")
        public_payload["selection_groups"] = _public_selection_groups(selection_groups)
    output_path.write_text(json.dumps(public_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


__all__ = [
    "BUNDLE_CONTEXT_NAME",
    "BUYOUT_FORBIDDEN_DIRS",
    "BUYOUT_FORBIDDEN_FILES",
    "BundleContext",
    "validate_agent_type",
    "VALID_AGENT_TYPES",
    "write_bundle_context",
]
