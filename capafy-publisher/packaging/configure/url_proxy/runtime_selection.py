from __future__ import annotations

from typing import Optional, TYPE_CHECKING

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


def _adapter_owns_structured_pair(pair: "UrlProxyPair", *, target_id: Optional[str]) -> bool:
    if not target_id:
        return False
    try:
        from packaging.runtimes.adapters import get_runtime_adapter_for_target

        adapter = get_runtime_adapter_for_target(target_id)
    except ValueError:
        return False
    if adapter.owns_structured_pair is not None:
        return adapter.owns_structured_pair(pair)
    group = str(getattr(pair, "group", "") or "").strip()
    return group.startswith(f"{adapter.runtime_id}/")


def runtime_owned_structured_pair(pair: "UrlProxyPair", *, target_id: Optional[str]) -> bool:
    if _adapter_owns_structured_pair(pair, target_id=target_id):
        return True
    return False


__all__ = [
    "is_runtime_applicable",
    "resolve_target_id",
    "runtime_context_target_id",
    "runtime_owned_structured_pair",
]
