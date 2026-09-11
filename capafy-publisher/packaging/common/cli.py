from __future__ import annotations

import json
from typing import Any, Optional


def emit_json_result(payload: dict, exit_code: int) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


def emit_json(payload: dict) -> int:
    return emit_json_result(payload, 0)


def fail(message: str) -> int:
    return emit_json_result(
        {
            "ok": False,
            "status": "error",
            "requires_action": False,
            "error": str(message),
        },
        1,
    )


def build_success(*, status: str, **extra: Any) -> dict[str, Any]:
    return {
        "ok": True,
        "status": status,
        "requires_action": False,
        **extra,
    }


def build_soft_action(
    *,
    status: str,
    action_type: str,
    next_step: Optional[str] = None,
    developer_next_steps: Optional[list[str]] = None,
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = dict(extra)
    payload.update({
        "ok": True,
        "status": status,
        "requires_action": True,
        "action_type": action_type,
    })
    if next_step:
        payload["next_step"] = next_step
    if developer_next_steps:
        payload["developer_next_steps"] = developer_next_steps
    return payload


def build_publish_error(
    *,
    error: str,
    failed_step: str,
    blocking_category: Optional[str] = None,
    developer_next_steps: Optional[list[str]] = None,
    next_step: Optional[str] = None,
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "status": "error",
        "requires_action": False,
        "error": error,
        "failed_step": failed_step,
    }
    if blocking_category:
        payload["blocking_category"] = blocking_category
    if developer_next_steps:
        payload["developer_next_steps"] = developer_next_steps
    if next_step:
        payload["next_step"] = next_step
    payload.update(extra)
    return payload


__all__ = [
    "build_publish_error",
    "build_soft_action",
    "build_success",
    "emit_json",
    "emit_json_result",
    "fail",
]
