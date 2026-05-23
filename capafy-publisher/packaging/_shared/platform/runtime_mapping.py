from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from packaging._shared.contracts.bundle_context import VALID_AGENT_TYPES

PACKAGE_REPORT_ALLOWED_STATUSES = {0, 2}

_DOCUMENTED_AGENT_RUNTIME_BY_ENV_ID = {
    "claude": "claude",
    "claude_code": "claude",
    "codex": "codex",
    "openclaw": "openclaw",
}
_DOCUMENTED_AGENT_RUNTIME_VARIANT_PREFIXES = (
    ("codex_", "codex"),
    ("openclaw_", "openclaw"),
)
_ENV_ID_BY_DOCUMENTED_AGENT_RUNTIME = {
    "claude": "claude_code",
    "claude_code": "claude_code",
    "codex": "codex",
    "openclaw": "openclaw",
}


def documented_agent_runtime_from_values(*values: object) -> str:
    for value in values:
        candidate = str(value or "").strip()
        if not candidate:
            continue
        runtime = _DOCUMENTED_AGENT_RUNTIME_BY_ENV_ID.get(candidate)
        if runtime:
            return runtime
        for prefix, family in _DOCUMENTED_AGENT_RUNTIME_VARIANT_PREFIXES:
            if candidate.startswith(prefix):
                return family
    return ""


def env_id_from_agent_runtime(agent_runtime: object) -> str:
    runtime = str(agent_runtime or "").strip()
    if not runtime:
        return ""
    env_id = _ENV_ID_BY_DOCUMENTED_AGENT_RUNTIME.get(runtime)
    if env_id:
        return env_id
    for prefix, family in _DOCUMENTED_AGENT_RUNTIME_VARIANT_PREFIXES:
        if runtime.startswith(prefix):
            return family
    return ""


def normalize_agent_type(agent_type: object) -> str:
    normalized = str(agent_type or "").strip().lower()
    if not normalized:
        return "run_online"
    if normalized not in VALID_AGENT_TYPES:
        raise ValueError(f"Unknown agentType: {agent_type}")
    return normalized


def _normalize_int(value: object) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    normalized = str(value or "").strip()
    if not normalized:
        return None
    try:
        return int(normalized)
    except ValueError:
        return None


def _is_confirmed(value: object) -> bool:
    normalized = _normalize_int(value)
    if normalized is not None:
        return normalized == 1
    normalized_text = str(value or "").strip().lower()
    return normalized_text == "true"


@dataclass(frozen=True)
class LatestVersion:
    agent_version_id: str
    env_id: str
    runtime_dir: str
    agent_type: str
    is_confirmed_skills: bool
    is_confirmed_config_keys: bool
    status: int
    url: str
    selection_groups: Dict[str, Any]
    required_credentials_payload: Optional[Dict[str, Any]]
    raw_payload: Dict[str, Any]


def _extract_env_context(latest: dict[str, Any]) -> tuple[str, str]:
    agent_runtime = (
        str(latest.get("agent_runtime", "")).strip()
        or str(latest.get("agentRuntime", "")).strip()
    )
    env_id = str(latest.get("env_id", "")).strip() or env_id_from_agent_runtime(agent_runtime)
    agent_type = normalize_agent_type(str(latest.get("agentType", "")))
    return env_id, agent_type


def parse_latest_version(payload: dict[str, Any]) -> LatestVersion:
    env_id, agent_type = _extract_env_context(payload)
    selection_groups = payload.get("selection_groups")
    required_credentials = payload.get("required_credentials_payload")
    runtime_dir = str(payload.get("runtime_dir", "")).strip()
    return LatestVersion(
        agent_version_id=str(payload.get("agentVersionId", "")).strip(),
        env_id=env_id,
        runtime_dir=runtime_dir,
        agent_type=agent_type,
        is_confirmed_skills=_is_confirmed(payload.get("isConfirmedSkills")),
        is_confirmed_config_keys=_is_confirmed(payload.get("isConfirmedConfigKeys")),
        status=_normalize_int(payload.get("status")) or 0,
        url=str(payload.get("url", "")).strip(),
        selection_groups=selection_groups if isinstance(selection_groups, dict) else {},
        required_credentials_payload=required_credentials if isinstance(required_credentials, dict) else None,
        raw_payload=dict(payload),
    )


__all__ = [
    "documented_agent_runtime_from_values",
    "env_id_from_agent_runtime",
    "LatestVersion",
    "PACKAGE_REPORT_ALLOWED_STATUSES",
    "normalize_agent_type",
    "parse_latest_version",
    "VALID_AGENT_TYPES",
]
