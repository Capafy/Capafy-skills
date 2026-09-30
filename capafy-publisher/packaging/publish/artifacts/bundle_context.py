from __future__ import annotations

from typing import Optional


VALID_AGENT_TYPES = frozenset({"run_online", "download"})
BUYOUT_FORBIDDEN_DIRS = {
    ".agents",
    ".claude",
    ".codex",
    ".config",
    ".openclaw",
    "skills",
    "workspace",
}
BUYOUT_FORBIDDEN_FILES = {
    "agent.runtime_dependencies.json",
}


def validate_agent_type(agent_type: Optional[str]) -> str:
    normalized = str(agent_type or "").strip()
    if not normalized:
        raise ValueError("agent_type must not be empty")
    if normalized not in VALID_AGENT_TYPES:
        raise ValueError(f"unknown agent_type: {normalized}")
    return normalized


__all__ = [
    "BUYOUT_FORBIDDEN_DIRS",
    "BUYOUT_FORBIDDEN_FILES",
    "validate_agent_type",
    "VALID_AGENT_TYPES",
]
