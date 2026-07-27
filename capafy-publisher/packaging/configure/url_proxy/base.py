from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Mapping, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from packaging.configure.candidate import Candidate
    from packaging.configure.contracts import UrlProxyPair
    from packaging.configure.staging.provider_runtime_config import ProviderRuntimeConfigContext


@dataclass(frozen=True)
class ScanContext:
    staging_root: Path
    process_env: Mapping[str, str]
    stage_plan: Any = None
    user_home: Optional[Path] = None
    provider_config_context: Optional["ProviderRuntimeConfigContext"] = None

    def scan_only_source_file(self, *relpaths: str) -> Optional[Path]:
        from packaging.configure.scan.stage_plan_sources import resolve_scan_only_source_file

        return resolve_scan_only_source_file(self.stage_plan, *relpaths)

    def scan_only_source_files_under(self, relpath: str) -> list[Path]:
        from packaging.configure.scan.stage_plan_sources import scan_only_source_files_under

        return scan_only_source_files_under(self.stage_plan, relpath)


class RuntimeContract(ABC):
    runtime_id: ClassVar[str]
    carries_provider_runtime_config: ClassVar[bool] = False

    def prepare_provider_runtime_config(
        self,
        staging_root: Path,
        *,
        provider_config_context: "ProviderRuntimeConfigContext",
    ) -> frozenset[str]:
        return frozenset()

    def os_fallback_environment_names(self) -> frozenset[str]:
        return frozenset()

    def validate_review_consistency(
        self,
        staging_root: Path,
        *,
        reviewed_scan: dict[str, Any],
    ) -> None:
        return None

    def semantic_field_identity(self, field_obj: Any) -> tuple[str, str, str]:
        return ("", "", "")

    def prepare(self, ctx: ScanContext) -> None:
        return None


    @abstractmethod
    def scan(self, ctx: ScanContext) -> list[Candidate]:
        pass

    @abstractmethod
    def pair(self, candidates: list[Candidate]) -> list[UrlProxyPair]:
        pass


    def rewrite(self, staging_root: Path, pairs: list[UrlProxyPair]) -> None:
        return None


    def rewrite_confirmed(self, staging_root: Path, reviewed_scan: dict[str, Any]) -> dict[str, Any]:
        return {}


__all__ = [
    "RuntimeContract",
    "ScanContext",
]
