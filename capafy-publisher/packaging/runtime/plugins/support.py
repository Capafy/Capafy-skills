from __future__ import annotations

import json
import re
from typing import Any, Mapping

from packaging.common.text_parse import looks_like_platform_managed_placeholder_value


_ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_ENV_TEMPLATE_RE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


def invalid_json_config_error(label: str, relpath: str, exc: json.JSONDecodeError) -> ValueError:
    return ValueError(
        f"invalid {label} JSON at {relpath}: "
        f"{exc.msg} (line {exc.lineno}, column {exc.colno})"
    )


def invalid_text_config_error(label: str, format_name: str, relpath: str, detail: str = "") -> ValueError:
    suffix = f": {detail}" if detail else ""
    return ValueError(f"invalid {label} {format_name} at {relpath}{suffix}")


def env_reference_name(value: object) -> str:
    if isinstance(value, Mapping):
        source = str(value.get("source", "") or "").strip().lower()
        if source != "env":
            return ""
        for field in ("id", "name", "key"):
            env_name = env_reference_name(value.get(field))
            if env_name:
                return env_name
        return ""
    normalized = usable_env_value(value)
    if not normalized:
        return ""
    if _ENV_NAME_RE.match(normalized):
        return normalized
    match = _ENV_TEMPLATE_RE.match(normalized)
    return match.group(1) if match else ""


def usable_env_value(value: object) -> str:
    normalized = str(value or "").strip()
    if not normalized or looks_like_platform_managed_placeholder_value(normalized):
        return ""
    return normalized


def usable_process_env_value(process_env: Any, field: str) -> str:
    get_value = getattr(process_env, "get", lambda _key, _default=None: _default)
    return usable_env_value(get_value(field, ""))
