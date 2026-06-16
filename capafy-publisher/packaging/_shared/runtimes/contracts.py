from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple, runtime_checkable

from packaging._shared.contracts.stage_plan import StagePlan


OPENCLAW_LEGACY_TARGET = "openclaw_legacy_native"
OPENCLAW_MODERN_TARGET = "openclaw_bundle_aware"


@dataclass(frozen=True)
class TargetDescriptor:
    target_id: str
    canonical_name: str
    profile_env_id: Optional[str] = None
    runtime_generation: Optional[str] = None
    runtime_variant: Optional[str] = None



CandidateAnnotator = Callable[..., Optional[dict]]

SpecialScanResult = Tuple[Dict[str, str], Dict[str, str], Dict[str, str], List[dict]]


@dataclass(frozen=True)
class RuntimeAdapter:
    runtime_id: str
    descriptors: Callable[[], tuple[TargetDescriptor, ...]]
    target_factory: Optional[Callable[[TargetDescriptor, dict], "PackagingTarget"]] = None
    url_proxy_runtime_factory: Optional[Callable[[], Any]] = None
    env_preprocess_hook: Optional[Callable[..., frozenset[str]]] = None
    owns_structured_pair: Optional[Callable[[Any], bool]] = None
    review_consistency_hook: Optional[Callable[..., None]] = None
    semantic_field_identity_hook: Optional[Callable[[Any], tuple[str, str, str]]] = None


@runtime_checkable
class PackagingTarget(Protocol):
    def profile_env_id(self) -> Optional[str]:
        ...

    def build_stage_plan(
        self,
        runtime_dir: str,
    ) -> StagePlan:
        ...

    def collect_runtime_environment_fields(self) -> dict:
        ...

    def prepare_runtime_dir(
        self,
        runtime_dir: str,
    ) -> str:
        ...

    def validate_runtime(
        self,
        runtime_root: Path,
        *,
        expected_version: Optional[str] = None,
    ) -> dict:
        ...


def call_optional_target_hook(
    target: Optional[object],
    method_name: str,
    *args: Any,
    default: Any = None,
    **kwargs: Any,
) -> Any:
    if target is None:
        return default
    method = getattr(target, method_name, None)
    if not callable(method):
        return default
    return method(*args, **kwargs)


__all__ = [
    "CandidateAnnotator",
    "OPENCLAW_LEGACY_TARGET",
    "OPENCLAW_MODERN_TARGET",
    "PackagingTarget",
    "RuntimeAdapter",
    "SpecialScanResult",
    "TargetDescriptor",
    "call_optional_target_hook",
]
