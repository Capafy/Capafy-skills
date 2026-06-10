from __future__ import annotations

import os
from typing import Any, Optional

from capafy_platform.api import list_agents_raw
from capafy_platform.http import get_last_request_error
from capafy_platform.token_store import load_persisted_access_token

from packaging._shared.common.cli import build_publish_error


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


__all__ = ["platform_login_error"]
