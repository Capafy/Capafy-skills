from __future__ import annotations
from typing import Optional

import json
from pathlib import Path

from packaging._shared.common.fs import path_basename
from packaging._shared.common.home import safe_expanduser_path
from packaging._shared.contracts.selectable import normalize_text
from packaging._shared.common.json_io import load_json_object


def _plugin_id_from_manifest(plugin_root: Path, payload: dict) -> str:
    for key in ("id", "name"):
        value = normalize_text(payload.get(key))
        if value:
            return value
    return plugin_root.name


def _plugin_channels_from_manifest(payload: dict, *, fallback_plugin_id: str) -> set[str]:
    channels: set[str] = set()
    raw_channels = payload.get("channels")
    if isinstance(raw_channels, list):
        for item in raw_channels:
            value = normalize_text(item)
            if value:
                channels.add(value)
    if fallback_plugin_id:
        channels.add(fallback_plugin_id)
    return channels


def _collect_local_plugin_descriptors(extensions_root: Path) -> dict[str, set[str]]:
    if not extensions_root.is_dir():
        return {}

    descriptors: dict[str, set[str]] = {}
    for child in sorted(extensions_root.iterdir(), key=lambda item: item.name):
        if not child.is_dir():
            continue
        manifest_path = child / "openclaw.plugin.json"
        if not manifest_path.is_file():
            continue
        manifest_payload = load_json_object(manifest_path)
        plugin_id = _plugin_id_from_manifest(child, manifest_payload)
        descriptors[plugin_id] = _plugin_channels_from_manifest(
            manifest_payload,
            fallback_plugin_id=plugin_id,
        )
    return descriptors


def _maybe_rewrite_packaged_load_path(value: str, packaged_plugin_ids: set[str]) -> Optional[str]:
    stripped = value.strip()
    if not stripped:
        return None
    normalized_check = stripped.replace("\\", "/").rstrip("/")
    basename = path_basename(stripped.rstrip("/\\"))
    if normalized_check == "~/.openclaw/extensions" or normalized_check.startswith("~/.openclaw/extensions/"):
        if basename and basename in packaged_plugin_ids:
            return f"~/.openclaw/extensions/{basename}"
        return None
    if basename and basename in packaged_plugin_ids:
        return f"~/.openclaw/extensions/{basename}"
    return None


def _filter_plugin_load_paths(payload: dict, *, packaged_plugin_ids: set[str]) -> int:
    plugins = payload.get("plugins")
    if not isinstance(plugins, dict):
        return 0
    load = plugins.get("load")
    if not isinstance(load, dict):
        return 0
    paths = load.get("paths")
    if not isinstance(paths, list):
        return 0

    new_paths: list[object] = []
    changes = 0
    for entry in paths:
        if not isinstance(entry, str):
            new_paths.append(entry)
            continue
        rewritten = _maybe_rewrite_packaged_load_path(entry, packaged_plugin_ids)
        if rewritten is None:
            changes += 1
            continue
        if rewritten != entry:
            new_paths.append(rewritten)
            changes += 1
        else:
            new_paths.append(entry)

    if changes:
        load["paths"] = new_paths
    return changes


def prune_unbundled_local_plugin_config(
    runtime_root: Path,
    *,
    source_extensions_root: Optional[Path] = None,
) -> int:
    config_path = runtime_root / ".openclaw" / "openclaw.json"
    if not config_path.is_file():
        return 0

    payload = load_json_object(config_path)
    if not payload:
        return 0

    changes = 0
    removed_plugin_ids: set[str] = set()

    channels = payload.get("channels")
    removed_channel_ids: set[str] = set()
    if isinstance(channels, dict):
        removed_channel_ids = {
            normalize_text(channel_id)
            for channel_id in channels
            if normalize_text(channel_id)
        }
        if "channels" in payload:
            del payload["channels"]
            changes += max(len(removed_channel_ids), 1)

    packaged_descriptors = _collect_local_plugin_descriptors(runtime_root / ".openclaw" / "extensions")
    packaged_plugin_ids = set(packaged_descriptors)

    resolved_source_root = safe_expanduser_path(source_extensions_root) if source_extensions_root is not None else None
    if resolved_source_root is not None and resolved_source_root.is_dir():
        source_plugins = _collect_local_plugin_descriptors(resolved_source_root)
        if source_plugins:
            removed_plugin_ids = set(source_plugins) - packaged_plugin_ids
            for plugin_id in removed_plugin_ids:
                removed_channel_ids.update(source_plugins.get(plugin_id, {plugin_id}))

    plugin_ids_to_remove = removed_plugin_ids | removed_channel_ids

    plugins = payload.get("plugins")
    if isinstance(plugins, dict):
        for field_name in ("entries", "installs"):
            group = plugins.get(field_name)
            if not isinstance(group, dict):
                continue
            for plugin_id in sorted(plugin_ids_to_remove):
                if plugin_id in group:
                    del group[plugin_id]
                    changes += 1
        allow_list = plugins.get("allow")
        if isinstance(allow_list, list):
            filtered_allow = [item for item in allow_list if normalize_text(item) not in plugin_ids_to_remove]
            if filtered_allow != allow_list:
                plugins["allow"] = filtered_allow
                changes += 1

    changes += _filter_plugin_load_paths(payload, packaged_plugin_ids=packaged_plugin_ids)

    if changes:
        config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changes


__all__ = ["prune_unbundled_local_plugin_config"]
