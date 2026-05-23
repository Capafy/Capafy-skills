from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Mapping

if TYPE_CHECKING:
    from packaging.configure.candidate import Candidate
    from packaging.configure.contracts import UrlProxyPair


@dataclass(frozen=True)
class ScanContext:
    staging_root: Path
    process_env: Mapping[str, str]
    stage_plan: Any = None
    user_home: Path | None = None
    target_id: str | None = None

    @property
    def scan_only_root(self) -> Path:
        return self.staging_root / "_scan_only"


class RuntimeContract(ABC):


    runtime_id: ClassVar[str]

    display_name: ClassVar[str]

    applicable_targets: ClassVar[frozenset[str] | None] = None


    def prepare(self, ctx: ScanContext) -> None:
        pass


    @abstractmethod
    def scan(self, ctx: ScanContext) -> list[Candidate]:
        pass

    @abstractmethod
    def pair(self, candidates: list[Candidate]) -> list[UrlProxyPair]:
        pass


    def rewrite(self, staging_root: Path, pairs: list[UrlProxyPair]) -> None:
        from packaging.configure.url_proxy.rewriter import apply_url_proxy_to_staging
        apply_url_proxy_to_staging(staging_root, pairs)


    def rewrite_confirmed(self, staging_root: Path, reviewed_scan: dict[str, Any]) -> dict[str, Any]:
        return {}


__all__ = [
    "RuntimeContract",
    "ScanContext",
]
