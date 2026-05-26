from __future__ import annotations

import re
from typing import Any, Mapping

from packaging.configure.sensitive.literals import looks_like_platform_managed_placeholder_value


_ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_ENV_TEMPLATE_RE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


def env_reference_name(value: object) -> str:
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


def resolve_env_reference_or_value(raw_value: object, env: Mapping[str, str]) -> str:
    value = usable_env_value(raw_value)
    if not value:
        return ""
    env_name = env_reference_name(value)
    if env_name:
        return usable_env_value(env.get(env_name, ""))
    return value
