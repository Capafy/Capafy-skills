from __future__ import annotations

from typing import Mapping, TypeVar


ModeT = TypeVar("ModeT")


def lookup_mode(registry: Mapping[str, ModeT], agent_type: str) -> ModeT:
    normalized = str(agent_type).strip()
    if not normalized:
        raise ValueError("Unknown agent_type: empty")
    try:
        return registry[normalized]
    except KeyError as exc:
        raise ValueError(f"Unknown agent_type: {agent_type}") from exc


__all__ = [
    "lookup_mode",
]
