from __future__ import annotations

import json
from typing import Any


def emit_json_result(payload: dict, exit_code: int) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


def emit_json(payload: dict) -> int:
    return emit_json_result(payload, 0)


def fail(message: str) -> int:
    return emit_json_result({"status": "error", "error": str(message)}, 1)


def build_publish_error(
    *,
    error: str,
    failed_step: str,
    blocking_category: str | None = None,
    developer_next_steps: list[str] | None = None,
    next_step: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "error",
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


def stopped_publish_payload(
    *,
    stop_reason: str,
    next_step: str,
    artifacts: dict[str, object],
    raw_steps: list[dict[str, object]],
    developer_next_steps: list[str] | None = None,
    missing_requirements: list[str] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "ok": False,
        "stopped": True,
        "stop_reason": stop_reason,
        "next_step": next_step,
        "requires_user_confirmation": False,
        "artifacts": artifacts,
        "raw_steps": raw_steps,
    }
    if developer_next_steps is not None:
        payload["developer_next_steps"] = developer_next_steps
    if missing_requirements is not None:
        payload["missing_requirements"] = missing_requirements
    return payload


__all__ = [
    "build_publish_error",
    "emit_json",
    "emit_json_result",
    "fail",
    "stopped_publish_payload",
]
