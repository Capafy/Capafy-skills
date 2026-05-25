from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Optional

from capafy_platform.api import get_account_me_raw
from capafy_platform.auth import login_init, login_verify
from packaging._shared.common.cli import emit_json, fail
from capafy_platform.token_store import (
    persist_access_token,
)


def _persist_agent_access_token(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {
            "token_persisted": False,
            "token_store_path": "",
        }
    access_token = str(payload.get("access_token", "")).strip()
    if not access_token:
        return {
            "token_persisted": False,
            "token_store_path": "",
        }
    return persist_access_token(
        access_token,
        user_id=str(payload.get("user_id", "")).strip(),
        email=str(payload.get("email", "")).strip(),
        name=str(payload.get("name", "")).strip(),
    )


def _platform_command(handler: Callable[..., dict[str, object]]) -> Callable[..., int]:
    @wraps(handler)
    def wrapped(*args: Any, **kwargs: Any) -> int:
        try:
            payload = handler(*args, **kwargs)
        except ValueError as exc:
            return fail(str(exc))
        return emit_json(payload)

    return wrapped


@_platform_command
def command_platform_login_init(
    email: str,
    *,
    base_url: Optional[str] = None,
) -> dict[str, object]:
    return login_init(email, base_url=base_url)


@_platform_command
def command_platform_login_verify(
    challenge_id: str,
    code: str,
    *,
    base_url: Optional[str] = None,
) -> dict[str, object]:
    payload = login_verify(challenge_id, code, base_url=base_url)
    payload.update(_persist_agent_access_token(payload))
    return payload


@_platform_command
def command_platform_login_token(
    access_token: str,
    *,
    base_url: Optional[str] = None,
) -> dict[str, object]:
    account_payload = get_account_me_raw(
        access_token=access_token,
        base_url=base_url,
    )
    persisted = persist_access_token(
        access_token,
        user_id=str(account_payload.get("userId", "")).strip(),
        email=str(account_payload.get("email", "")).strip(),
        name=str(account_payload.get("name", "")).strip(),
    )
    return {
        "status": "token_persisted",
        **persisted,
    }


__all__ = [
    "command_platform_login_init",
    "command_platform_login_token",
    "command_platform_login_verify",
]
