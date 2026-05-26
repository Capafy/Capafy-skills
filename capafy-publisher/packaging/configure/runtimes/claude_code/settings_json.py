from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from packaging.configure.dotenv import remove_dotenv_keys_text
from packaging.configure.runtimes.claude_code.url_proxy_candidates import (
    MODEL_DOTENV_RELPATHS,
    MODEL_ENV_FIELDS,
    SETTINGS_SCAN_RELPATHS,
    resolve_settings_model,
)

if TYPE_CHECKING:
    from packaging.configure.staging.env_preprocess import RuntimeEnvContext


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


def _prune_settings_env_models(payload: dict) -> bool:
    env_payload = payload.get("env")
    if not isinstance(env_payload, dict):
        return False
    changed = False
    for field in MODEL_ENV_FIELDS:
        if field in env_payload:
            env_payload.pop(field, None)
            changed = True
    return changed


def _prune_non_primary_settings_env_models(staging_root: Path) -> bool:
    changed = False
    for relpath in SETTINGS_SCAN_RELPATHS:
        if relpath == SETTINGS_RELPATH:
            continue
        path = staging_root / relpath
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        if not _prune_settings_env_models(payload):
            continue
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        changed = True
    return changed


def _prune_dotenv_model_keys(staging_root: Path) -> bool:
    changed = False
    for relpath in MODEL_DOTENV_RELPATHS:
        path = staging_root / relpath
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        updated_text, file_changed = remove_dotenv_keys_text(text, MODEL_ENV_FIELDS)
        if not file_changed:
            continue
        path.write_text(updated_text, encoding="utf-8")
        changed = True
    return changed


def write_settings_model_and_prune_env_models(
    staging_root: Path,
    model: str,
    *,
    prune_dotenv: bool = True,
) -> bool:
    payload = read_settings_payload(staging_root)
    changed = False
    if str(payload.get("model", "") or "").strip() != model:
        payload["model"] = model
        changed = True
    changed = _prune_settings_env_models(payload) or changed
    if changed:
        write_settings_payload(staging_root, payload)
    changed = _prune_non_primary_settings_env_models(staging_root) or changed
    if prune_dotenv:
        changed = _prune_dotenv_model_keys(staging_root) or changed
    return changed


def preprocess_settings_model_env(
    staging_root: Path,
    *,
    env_context: "RuntimeEnvContext",
) -> frozenset[str]:
    dotenv_env = env_context.staged_dotenv_values(
        staging_root,
        relpaths=MODEL_DOTENV_RELPATHS,
        names=frozenset(MODEL_ENV_FIELDS),
    )
    merged_process_env = dict(dotenv_env)
    merged_process_env.update(env_context.env_for_names(frozenset(MODEL_ENV_FIELDS)))
    model = resolve_settings_model(staging_root, merged_process_env)
    if not model or model.kind == "settings":
        return frozenset()
    write_settings_model_and_prune_env_models(staging_root, model.value, prune_dotenv=False)
    if model.kind == "dotenv":
        env_context.consume_staged_dotenv_names(
            staging_root,
            relpaths=MODEL_DOTENV_RELPATHS,
            names=frozenset({model.field}),
        )
    return frozenset({model.field}) if model.field else frozenset()


__all__ = [
    "SETTINGS_LOCAL_RELPATH",
    "SETTINGS_RELPATH",
    "drop_settings_local_permissions",
    "preprocess_settings_model_env",
    "read_settings_payload",
    "write_settings_env_placeholders",
    "write_settings_model_and_prune_env_models",
    "write_settings_model",
    "write_settings_payload",
]
