from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from packaging.configure.runtimes.claude_code.url_proxy_candidates import SETTINGS_SCAN_RELPATHS
from packaging.configure.url_proxy.base import RuntimeContract

if TYPE_CHECKING:
    from packaging.configure.contracts import UrlProxyPair


def resolve_target_id(env_id: str) -> str:
    try:
        from packaging.runtimes.registry import get_target_descriptor
        descriptor = get_target_descriptor(env_id)
        return descriptor.target_id
    except (ImportError, KeyError, ValueError):
        return env_id


def _target_match_names(env_id: str) -> frozenset[str]:
    normalized = str(env_id or "").strip()
    names: set[str] = {normalized} if normalized else set()
    try:
        from packaging.runtimes.registry import get_target_descriptor
        descriptor = get_target_descriptor(normalized)
    except (ImportError, KeyError, ValueError):
        return frozenset(names)

    for value in (
        descriptor.target_id,
        descriptor.canonical_name,
        descriptor.profile_env_id,
        descriptor.runtime_generation,
    ):
        name = str(value or "").strip()
        if name:
            names.add(name)
    return frozenset(names)


def is_runtime_applicable(runtime: RuntimeContract, env_id: Optional[str]) -> bool:
    if env_id is None:
        return True
    targets = runtime.applicable_targets
    if targets is None:
        return True
    return bool(_target_match_names(env_id) & set(targets))


def runtime_context_target_id(env_id: Optional[str]) -> Optional[str]:
    if env_id is None:
        return None
    match_names = _target_match_names(env_id)
    resolved_target_id = resolve_target_id(env_id)
    return resolved_target_id if resolved_target_id in match_names else str(env_id or "").strip()


_CLAUDE_SETTINGS_RELPATHS = frozenset(SETTINGS_SCAN_RELPATHS)
_OPENCLAW_PROVIDER_GROUP_PREFIX = ".openclaw/openclaw.json#models.providers."


def runtime_owned_structured_pair(pair: "UrlProxyPair", *, target_id: Optional[str]) -> bool:
    key_source = str(getattr(pair.key, "source_relpath", "") or "").strip()
    url_source = str(getattr(pair.url, "source_relpath", "") or "").strip()
    if target_id == "claude_code":
        return key_source in _CLAUDE_SETTINGS_RELPATHS or url_source in _CLAUDE_SETTINGS_RELPATHS
    if target_id == "openclaw":
        group = str(getattr(pair, "group", "") or "").strip()
        return group.startswith(_OPENCLAW_PROVIDER_GROUP_PREFIX)
    return False


__all__ = [
    "is_runtime_applicable",
    "resolve_target_id",
    "runtime_context_target_id",
    "runtime_owned_structured_pair",
]
