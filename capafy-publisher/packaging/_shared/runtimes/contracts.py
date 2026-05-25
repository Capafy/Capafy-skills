from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple, runtime_checkable

from packaging._shared.contracts.stage_plan import StagePlan


@dataclass(frozen=True)
class TargetDescriptor:
    target_id: str
    canonical_name: str
    profile_env_id: Optional[str] = None
    runtime_generation: Optional[str] = None
    runtime_variant: Optional[str] = None
    feature_tags: tuple[str, ...] = ()



CandidateAnnotator = Callable[..., Optional[dict]]

SpecialScanResult = Tuple[Dict[str, str], Dict[str, str], Dict[str, str], List[dict]]


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
    "PackagingTarget",
    "SpecialScanResult",
    "TargetDescriptor",
    "call_optional_target_hook",
]
