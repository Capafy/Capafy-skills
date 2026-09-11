from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from capafy_platform.api import list_agents_raw
from capafy_platform.http import get_last_request_error
from capafy_platform.token_store import load_persisted_access_token
from packaging.common.cli import build_publish_error
from packaging.runtime.profiles import load_profile
from packaging.runtime import build_runtime_metadata, get_target


def _latest_request_http_status() -> int:
    error = get_last_request_error()
    if not isinstance(error, dict):
        return -1
    try:
        return int(error.get("http_status", -1))
    except (TypeError, ValueError):
        return -1


def platform_login_error() -> Optional[dict[str, Any]]:
    env_token = str(os.environ.get("CAPAFY_ACCESS_TOKEN", "") or "").strip()
    persisted = None
    try:
        if not env_token:
            persisted = load_persisted_access_token()
    except ValueError as exc:
        return build_publish_error(
            error=f"platform login state is invalid: {exc}",
            failed_step="check_platform_login",
            blocking_category="platform_login_invalid",
            developer_next_steps=[
                "Run login-init/login-verify or login-token again, then rerun publish-init.",
            ],
            next_step="login_then_retry_publish_init",
        )

    if not env_token and persisted is None:
        return build_publish_error(
            error="platform login is required before publish-init",
            failed_step="check_platform_login",
            blocking_category="platform_login_required",
            developer_next_steps=[
                "Run login-init/login-verify or login-token, then rerun publish-init.",
            ],
            next_step="login_then_retry_publish_init",
        )

    try:
        list_agents_raw()
    except Exception as exc:
        http_status = _latest_request_http_status()
        if http_status == 0 or http_status >= 500:
            return build_publish_error(
                error=f"platform login check could not reach the platform: {exc}",
                failed_step="check_platform_login",
                blocking_category="platform_login_check_unreachable",
                developer_next_steps=[
                    "Check the network connection and platform availability, then rerun publish-init.",
                ],
                next_step="retry_platform_login_check",
            )
        return build_publish_error(
            error=f"platform login state is not usable: {exc}",
            failed_step="check_platform_login",
            blocking_category="platform_login_invalid",
            developer_next_steps=[
                "Run login-init/login-verify or login-token again, then rerun publish-init.",
            ],
            next_step="login_then_retry_publish_init",
        )
    return None


def prepare_environment(
    env_name: str,
    *,
    runtime_dir: str,
) -> dict:
    normalized_env_name = str(env_name or "").strip()
    if not normalized_env_name:
        raise ValueError("env_name is required")

    normalized_runtime_dir = str(runtime_dir or "").strip()
    if not normalized_runtime_dir:
        raise ValueError("runtime_dir is required")
    normalized_runtime_dir = str(Path(normalized_runtime_dir).expanduser())

    target = get_target(normalized_env_name)
    profile_env_name = str(target.profile_env_id() or normalized_env_name).strip()
    if not profile_env_name:
        raise ValueError(f"{normalized_env_name} does not declare a profile environment id")

    load_profile(profile_env_name)
    normalized_runtime_dir = target.prepare_runtime_dir(normalized_runtime_dir)

    payload = {
        "env_id": normalized_env_name,
        "runtime_dir": normalized_runtime_dir,
    }
    payload.update(build_runtime_metadata(normalized_env_name))
    return payload


__all__ = [
    "platform_login_error",
    "prepare_environment",
]
