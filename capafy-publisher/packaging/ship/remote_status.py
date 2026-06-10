from __future__ import annotations

from typing import Any

from capafy_platform.api import get_latest_version_raw, list_agents_raw
from packaging._shared.common.cli import build_publish_error, emit_json_result


def run_publish_remote_status(*, agent_id: str) -> tuple[dict[str, Any], int]:
    normalized_agent_id = str(agent_id or "").strip()
    if not normalized_agent_id:
        return build_publish_error(
            error="agent_id must not be empty",
            failed_step="read_remote_status",
        ), 1
    latest_version = get_latest_version_raw(normalized_agent_id)
    return {
        "ok": True,
        "status": "remote_status",
        "status_scope": "platform_latest_version",
        "agent_id": normalized_agent_id,
        "latest_version": latest_version,
    }, 0


def run_publish_list() -> tuple[dict[str, Any], int]:
    agents = list_agents_raw()
    return {
        "ok": True,
        "status": "agents_list",
        "status_scope": "platform_account",
        "agents": agents,
    }, 0


def publish_remote_status(agent_id: str) -> int:
    payload, code = run_publish_remote_status(agent_id=agent_id)
    return emit_json_result(payload, code)


def publish_list() -> int:
    payload, code = run_publish_list()
    return emit_json_result(payload, code)


__all__ = [
    "publish_list",
    "publish_remote_status",
    "run_publish_list",
    "run_publish_remote_status",
]
