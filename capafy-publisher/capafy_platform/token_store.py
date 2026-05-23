from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packaging._shared.common.constants import SKILL_CONFIG_PATH
from packaging._shared.common.fs import safe_chmod


def token_store_path() -> Path:
    return SKILL_CONFIG_PATH.resolve()


def persist_access_token(
    access_token: str,
    *,
    user_id: str | None = None,
    email: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    normalized_access_token = str(access_token or "").strip()
    if not normalized_access_token:
        raise ValueError("access_token must not be empty")

    store_path = token_store_path()
    store_path.parent.mkdir(parents=True, exist_ok=True)
    safe_chmod(store_path.parent, 0o700)

    payload = {
        "access_token": normalized_access_token,
        "user_id": str(user_id or "").strip(),
        "email": str(email or "").strip(),
        "name": str(name or "").strip(),
    }
    store_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    safe_chmod(store_path, 0o600)
    return {
        "token_persisted": True,
        "token_store_path": str(store_path),
    }


def _load_persisted_token_payload() -> tuple[dict[str, Any], Path] | None:
    store_path = token_store_path()
    if not store_path.is_file():
        return None
    try:
        payload = json.loads(store_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"failed to parse local token file: {store_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"local token file top-level value must be an object: {store_path}")
    return payload, store_path


def load_persisted_access_token() -> tuple[str, Path] | None:
    loaded = _load_persisted_token_payload()
    if loaded is None:
        return None
    payload, store_path = loaded
    access_token = str(payload.get("access_token", "")).strip()
    if not access_token:
        raise ValueError(f"local token file is missing access_token: {store_path}")
    return access_token, store_path


__all__ = [
    "load_persisted_access_token",
    "persist_access_token",
    "token_store_path",
]
