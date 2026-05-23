from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packaging._shared.common.local_path_detection import (
    LOCAL_PATH_PLACEHOLDER,
    redact_local_traces_in_text,
)
from packaging._shared.contracts.stage_plan import StagePlan
from packaging._shared.contracts.selectable import normalize_text
from packaging._shared.policies.path_refs import build_packaged_runtime_ref


RUNTIME_ENVIRONMENT_MANIFEST_NAME = "agent.runtime_environment.json"
OPENCLAW_CONFIG_MODE_OVERLAY_MERGE = "overlay_merge"

_WORKSPACE_DOCUMENT_PATH_FIELDS = (
    ("memory", "qmd", "paths"),
    ("memorySearch", "extraPaths"),
)

_OVERLAY_TOP_LEVEL_FIELDS = (
    "models",
    "agents",
    "channels",
    "memory",
    "memorySearch",
    "skills",
    "plugins",
    "env",
)


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _clone_json_value(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _clone_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clone_json_value(item) for item in value]
    return value


def _merge_json_patch(base: object, overlay: object) -> object:
    if isinstance(overlay, dict):
        merged: dict[str, object] = {}
        if isinstance(base, dict):
            merged.update({str(key): _clone_json_value(value) for key, value in base.items()})
        for key, value in overlay.items():
            normalized_key = str(key)
            if value is None:
                merged.pop(normalized_key, None)
                continue
            merged[normalized_key] = _merge_json_patch(merged.get(normalized_key), value)
        return merged
    if isinstance(overlay, list):
        return [_clone_json_value(item) for item in overlay]
    return overlay


def _is_openclaw_overlay_runtime(runtime_root: Path) -> bool:
    payload = _load_json_object(runtime_root / RUNTIME_ENVIRONMENT_MANIFEST_NAME)
    return normalize_text(payload.get("openclaw_config_mode")) == OPENCLAW_CONFIG_MODE_OVERLAY_MERGE


def _iter_confirmed_workspace_document_entries(payload: dict) -> list[dict]:
    entries: list[dict] = []
    raw_items = payload.get("workspace_documents", [])
    if not isinstance(raw_items, list):
        return entries
    for item in raw_items:
        if isinstance(item, dict):
            entries.append(item)
    return entries


def _build_openclaw_config_overlay(payload: dict) -> dict:
    overlay: dict[str, object] = {}
    for key in _OVERLAY_TOP_LEVEL_FIELDS:
        if key not in payload:
            continue
        overlay[key] = _clone_json_value(payload.get(key))

    tools = payload.get("tools")
    if isinstance(tools, dict):
        media = tools.get("media")
        if isinstance(media, dict):
            audio = media.get("audio")
            if audio is not None:
                overlay["tools"] = {
                    "media": {
                        "audio": _clone_json_value(audio),
                    }
                }
    return overlay


def rewrite_packaged_openclaw_config_as_overlay(runtime_root: Path) -> int:
    config_path = runtime_root / ".openclaw" / "openclaw.json"
    if not config_path.is_file():
        return 0

    payload = _load_json_object(config_path)
    if not payload:
        return 0

    overlay = _build_openclaw_config_overlay(payload)
    if overlay == payload:
        return 0

    removed_root_fields = len(set(payload) - set(overlay))
    config_path.write_text(json.dumps(overlay, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return removed_root_fields or 1


def merge_openclaw_overlay_with_base(
    runtime_root: Path,
    *,
    base_config_path: Path | None = None,
) -> dict[str, object]:
    config_path = runtime_root / ".openclaw" / "openclaw.json"
    if not config_path.is_file():
        return {
            "mode": "missing_overlay",
            "used_base_config": False,
            "changed": False,
        }

    overlay_payload = _load_json_object(config_path)
    if not overlay_payload:
        return {
            "mode": "invalid_overlay",
            "used_base_config": False,
            "changed": False,
        }

    if not _is_openclaw_overlay_runtime(runtime_root):
        return {
            "mode": "direct",
            "used_base_config": False,
            "changed": False,
        }

    base_payload = _load_json_object(base_config_path) if base_config_path is not None and base_config_path.is_file() else {}
    used_base_config = bool(base_payload)
    merged_payload = _merge_json_patch(base_payload, overlay_payload)
    changed = merged_payload != overlay_payload
    if changed:
        config_path.write_text(json.dumps(merged_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "mode": "overlay_merge" if used_base_config else "overlay_only",
        "used_base_config": used_base_config,
        "changed": changed,
        "base_config_path": str(base_config_path) if used_base_config and base_config_path is not None else "",
    }


def _resolved_path_text(raw_path: str) -> str:
    normalized = normalize_text(raw_path)
    if not normalized or "://" in normalized:
        return ""
    try:
        return str(Path(normalized).expanduser().resolve(strict=False))
    except OSError:
        return ""


def _entry_matches_path(raw_path: str, entry: dict) -> bool:
    normalized = normalize_text(raw_path)
    if not normalized:
        return False

    packaged_ref = build_packaged_runtime_ref(str(entry.get("packaged_path", "")))
    if normalized == packaged_ref:
        return True

    resolved_candidate = _resolved_path_text(normalized)
    resolved_source_path = normalize_text(entry.get("resolved_source_path"))
    return bool(resolved_candidate and resolved_source_path and resolved_candidate == resolved_source_path)


def _matching_entry(raw_path: str, entries: list[dict]) -> dict | None:
    for entry in entries:
        if _entry_matches_path(raw_path, entry):
            return entry
    return None


def _config_path_lists(payload: dict) -> list[tuple[str, list]]:
    groups: list[tuple[str, list]] = []
    for parts in _WORKSPACE_DOCUMENT_PATH_FIELDS:
        node: object = payload
        for part in parts:
            if not isinstance(node, dict):
                node = None
                break
            node = node.get(part)
        if isinstance(node, list):
            groups.append((".".join(parts), node))
    return groups


def _path_value_from_config_item(item: object) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        value = item.get("path")
        if isinstance(value, str):
            return value
    return ""


def _set_path_value_for_config_item(values: list, index: int, packaged_ref: str) -> bool:
    item = values[index]
    if isinstance(item, str):
        if item == packaged_ref:
            return False
        values[index] = packaged_ref
        return True
    if isinstance(item, dict):
        if item.get("path") == packaged_ref:
            return False
        item["path"] = packaged_ref
        return True
    return False


def _discover_packaged_workspace_name(runtime_root: Path) -> str | None:
    openclaw_root = runtime_root / ".openclaw"
    if not openclaw_root.is_dir():
        return None

    workspace_dirs = sorted(
        child.name
        for child in openclaw_root.iterdir()
        if child.is_dir() and child.name.startswith("workspace")
    )
    if "workspace" in workspace_dirs:
        return "workspace"
    if len(workspace_dirs) == 1:
        return workspace_dirs[0]
    return None


def _build_packaged_workspace_ref(workspace_name: str) -> str:
    return f"~/.openclaw/{workspace_name}"


def _rewrite_workspace_field(container: dict, packaged_ref: str) -> int:
    workspace_value = container.get("workspace")
    if not isinstance(workspace_value, str) or workspace_value == packaged_ref:
        return 0
    container["workspace"] = packaged_ref
    return 1


def rewrite_packaged_workspace_ref(
    runtime_root: Path,
    *,
    workspace_name: str | None = None,
) -> int:
    config_path = runtime_root / ".openclaw" / "openclaw.json"
    if not config_path.is_file():
        return 0

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0

    resolved_workspace_name = workspace_name or _discover_packaged_workspace_name(runtime_root)
    if not resolved_workspace_name:
        return 0

    agents = payload.get("agents")
    if not isinstance(agents, dict):
        return 0

    rewrites = 0
    defaults = agents.get("defaults")
    packaged_ref = _build_packaged_workspace_ref(resolved_workspace_name)
    if isinstance(defaults, dict):
        rewrites += _rewrite_workspace_field(defaults, packaged_ref)

    agent_list = agents.get("list")
    if isinstance(agent_list, list):
        for agent in agent_list:
            if isinstance(agent, dict):
                rewrites += _rewrite_workspace_field(agent, packaged_ref)

    if rewrites:
        config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rewrites


def _extra_skill_dir_ref_map(stage_plan: StagePlan) -> dict[str, str]:
    refs: dict[str, str] = {}
    for tree_source in stage_plan.tree_sources:
        if tree_source.source_value != "extra_skill_dir":
            continue
        try:
            source_path = str(tree_source.source_root.expanduser().resolve())
        except OSError:
            source_path = str(tree_source.source_root.expanduser())
        packaged_ref = build_packaged_runtime_ref(tree_source.relative_target_root.as_posix())
        refs[source_path] = packaged_ref
    return refs


def _resolved_extra_dir_text(raw_path: str) -> str:
    normalized = normalize_text(raw_path)
    if not normalized or "://" in normalized:
        return ""
    try:
        return str(Path(normalized).expanduser().resolve(strict=False))
    except OSError:
        return ""


def rewrite_packaged_extra_skill_dirs(runtime_root: Path, stage_plan: StagePlan) -> int:
    config_path = runtime_root / ".openclaw" / "openclaw.json"
    if not config_path.is_file():
        return 0

    payload = _load_json_object(config_path)
    if not payload:
        return 0

    refs = _extra_skill_dir_ref_map(stage_plan)
    if not refs:
        return 0
    packaged_refs = {
        str(packaged_ref).replace("\\", "/").rstrip("/")
        for packaged_ref in refs.values()
    }

    skills = payload.get("skills")
    if not isinstance(skills, dict):
        return 0
    load = skills.get("load")
    if not isinstance(load, dict):
        return 0
    extra_dirs = load.get("extraDirs")
    if not isinstance(extra_dirs, list):
        return 0

    rewrites = 0
    for index, item in enumerate(extra_dirs):
        if not isinstance(item, str):
            continue
        normalized_item = item.strip().replace("\\", "/").rstrip("/")
        if normalized_item in packaged_refs:
            continue
        packaged_ref = refs.get(_resolved_extra_dir_text(item))
        if packaged_ref and item != packaged_ref:
            extra_dirs[index] = packaged_ref
            rewrites += 1
            continue
        redacted_item, redactions = redact_local_traces_in_text(
            item,
            replacement=LOCAL_PATH_PLACEHOLDER,
        )
        if redactions and redacted_item != item:
            extra_dirs[index] = redacted_item
            rewrites += 1

    if rewrites:
        config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rewrites


def rewrite_packaged_workspace_document_refs(
    runtime_root: Path,
    *,
    workspace_documents_manifest_payload: dict[str, Any] | None = None,
) -> int:
    config_path = runtime_root / ".openclaw" / "openclaw.json"
    if not config_path.is_file():
        return 0

    payload = _load_json_object(config_path)
    if not payload:
        return 0

    if not workspace_documents_manifest_payload:
        return 0

    entries = _iter_confirmed_workspace_document_entries(workspace_documents_manifest_payload)
    if not entries:
        return 0

    rewrites = 0
    for _field_name, values in _config_path_lists(payload):
        for index, item in enumerate(values):
            raw_value = _path_value_from_config_item(item)
            if not raw_value:
                continue
            entry = _matching_entry(raw_value, entries)
            if entry is not None:
                packaged_ref = build_packaged_runtime_ref(str(entry.get("packaged_path", "")))
                if packaged_ref and _set_path_value_for_config_item(values, index, packaged_ref):
                    rewrites += 1
                continue
            redacted_value, redactions = redact_local_traces_in_text(
                raw_value,
                replacement=LOCAL_PATH_PLACEHOLDER,
            )
            if redactions and redacted_value != raw_value and _set_path_value_for_config_item(values, index, redacted_value):
                rewrites += 1

    if rewrites:
        config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rewrites


def validate_packaged_workspace_document_refs(
    runtime_root: Path,
    *,
    workspace_documents_manifest_payload: dict[str, Any] | None = None,
) -> list[str]:
    if not workspace_documents_manifest_payload:
        return []

    errors: list[str] = []
    seen: set[str] = set()
    entries = _iter_confirmed_workspace_document_entries(workspace_documents_manifest_payload)
    for entry in entries:
        source_path = normalize_text(entry.get("source_path")) or normalize_text(entry.get("resolved_source_path"))
        packaged_path = normalize_text(entry.get("packaged_path"))
        if not packaged_path:
            message = f"confirmed workspace document is missing packaged_path: {source_path or 'unknown'}"
            if message not in seen:
                seen.add(message)
                errors.append(message)
            continue
        if not (runtime_root / packaged_path).exists():
            message = f"confirmed workspace document packaged path does not exist: {packaged_path} (source: {source_path or 'unknown'})"
            if message not in seen:
                seen.add(message)
                errors.append(message)

    config_path = runtime_root / ".openclaw" / "openclaw.json"
    if not config_path.is_file():
        return errors

    payload = _load_json_object(config_path)
    if not payload:
        return errors

    for field_name, values in _config_path_lists(payload):
        for index, item in enumerate(values):
            raw_value = _path_value_from_config_item(item)
            if not raw_value:
                continue
            entry = _matching_entry(raw_value, entries)
            if entry is None:
                continue
            packaged_ref = build_packaged_runtime_ref(str(entry.get("packaged_path", "")))
            if packaged_ref and normalize_text(raw_value) != packaged_ref:
                message = (
                    f"openclaw.{field_name}[{index}] was not rewritten to a packaged path: "
                    f"{normalize_text(raw_value)} -> {packaged_ref}"
                )
                if message not in seen:
                    seen.add(message)
                    errors.append(message)

    return errors


__all__ = [
    "OPENCLAW_CONFIG_MODE_OVERLAY_MERGE",
    "merge_openclaw_overlay_with_base",
    "rewrite_packaged_extra_skill_dirs",
    "rewrite_packaged_workspace_document_refs",
    "rewrite_packaged_openclaw_config_as_overlay",
    "rewrite_packaged_workspace_ref",
    "validate_packaged_workspace_document_refs",
]
