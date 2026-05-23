from __future__ import annotations

import json
from pathlib import Path


SETTINGS_RELPATH = ".claude/settings.json"
SETTINGS_LOCAL_RELPATH = ".claude/settings.local.json"


def read_settings_payload(staging_root: Path) -> dict:
    settings_path = staging_root / SETTINGS_RELPATH
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        return {}
    return payload


def write_settings_payload(staging_root: Path, payload: dict) -> None:
    settings_path = staging_root / SETTINGS_RELPATH
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def drop_settings_local_permissions(staging_root: Path) -> int:
    settings_path = staging_root / SETTINGS_LOCAL_RELPATH
    if not settings_path.is_file():
        return 0
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    if not isinstance(payload, dict) or "permissions" not in payload:
        return 0
    updated = dict(payload)
    del updated["permissions"]
    settings_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1


def write_settings_env_placeholders(
    staging_root: Path,
    *,
    key_field: str,
    key_placeholder: str,
    url_placeholder: str,
    api_key_fields: frozenset[str],
    canonical_base_url_field: str,
) -> None:
    payload = read_settings_payload(staging_root)
    env_payload = payload.get("env")
    if not isinstance(env_payload, dict):
        env_payload = {}
    for key in api_key_fields - {key_field}:
        payload.pop(key, None)
        env_payload.pop(key, None)
    payload.pop(key_field, None)
    payload.pop(canonical_base_url_field, None)
    env_payload[key_field] = key_placeholder
    env_payload[canonical_base_url_field] = url_placeholder
    payload["env"] = env_payload
    write_settings_payload(staging_root, payload)


def write_settings_model(staging_root: Path, model: str) -> bool:
    payload = read_settings_payload(staging_root)
    if str(payload.get("model", "") or "").strip() == model:
        return False
    payload["model"] = model
    write_settings_payload(staging_root, payload)
    return True


__all__ = [
    "SETTINGS_LOCAL_RELPATH",
    "SETTINGS_RELPATH",
    "drop_settings_local_permissions",
    "read_settings_payload",
    "write_settings_env_placeholders",
    "write_settings_model",
    "write_settings_payload",
]
