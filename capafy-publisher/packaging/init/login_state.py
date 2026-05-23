from __future__ import annotations

import os
from typing import Any

from capafy_platform.api import list_agents_raw
from capafy_platform.token_store import load_persisted_access_token

from packaging._shared.common.cli import build_publish_error


def platform_login_error() -> dict[str, Any] | None:
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
