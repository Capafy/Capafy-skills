from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import hashlib
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Optional, Protocol, runtime_checkable

from packaging.runtime.stage_plan import StagePlan


class SourceKind(str, Enum):
    FILE = "file"
    PROCESS_ENV = "process_env"
    SYNTHESIZED = "synthesized"


PROCESS_ENV_SOURCE = "process.env"


@dataclass(frozen=True)
class FieldLocation:
    fmt: Literal["dotenv", "json", "toml", "yaml"]
    occurrence_index: int = 0
    line_number: int = 0
    json_pointer: str = ""
    toml_section: str = ""
    key_path: tuple[str, ...] = ()

    def to_source_detail(self, field: str = "") -> str:
        if self.fmt == "dotenv" and self.line_number > 0:
            return f"line {self.line_number}"
        if self.fmt == "json" and self.json_pointer:
            return f"json:{self.json_pointer}"
        if self.fmt == "toml":
            section = str(self.toml_section or "").strip()
            field_name = str(field or "").strip()
            if section and field_name:
                return f"toml:{section}.{field_name}"
            if section:
                return f"toml:{section}"
            if field_name:
                return f"toml:{field_name}"
        if self.fmt == "yaml":
            parts = tuple(str(part or "").strip() for part in self.key_path if str(part or "").strip())
            if parts:
                return "yaml:" + ".".join(parts)
            field_name = str(field or "").strip()
            if field_name:
                return f"yaml:{field_name}"
        return ""

    def occurrence_index_identity(self) -> int:
        return self.occurrence_index if self.occurrence_index > 0 else 1

    @classmethod
    def from_source_detail(cls, source_detail: str, *, field: str = "") -> "FieldLocation":
        detail = str(source_detail or "").strip()
        if detail.startswith("json:"):
            return cls(fmt="json", json_pointer=detail[len("json:") :])
        if detail.startswith("toml:"):
            toml_path = detail[len("toml:") :].strip()
            field_name = str(field or "").strip()
            if field_name and toml_path == field_name:
                toml_path = ""
            elif field_name and toml_path.endswith(f".{field_name}"):
                toml_path = toml_path[: -(len(field_name) + 1)]
            return cls(fmt="toml", toml_section=toml_path)
        if detail.startswith("yaml:"):
            return cls(fmt="yaml", key_path=tuple(part for part in detail[len("yaml:") :].strip().split(".") if part))
        if detail.startswith("line "):
            try:
                line_number = int(detail.split(" ", 1)[1].strip())
            except (IndexError, ValueError):
                line_number = 0
            return cls(fmt="dotenv", line_number=max(line_number, 0))
        return cls(fmt="json")


@dataclass(frozen=True)
class PlanField:
    field: str
    service: str
    source_kind: SourceKind
    source_relpath: str
    location: Optional[FieldLocation]
    original_value: str
    placeholder: str
    reviewed_source: str = ""
    reviewed_source_detail: str = ""
    reviewed_occurrence_index: int = 1

    def source_identity(self) -> str:
        if self.reviewed_source:
            return self.reviewed_source
        if self.source_kind == SourceKind.FILE:
            return self.source_relpath
        if self.source_kind == SourceKind.PROCESS_ENV:
            return PROCESS_ENV_SOURCE
        if self.source_kind == SourceKind.SYNTHESIZED:
            return f"<synthesized:{self.service}>"
        raise ValueError(f"unknown source_kind: {self.source_kind}")

    def source_detail_identity(self) -> str:
        if self.reviewed_source_detail:
            return self.reviewed_source_detail
        return self.location.to_source_detail(self.field) if self.location else ""

    def occurrence_index_identity(self) -> int:
        try:
            value = int(self.reviewed_occurrence_index)
        except (TypeError, ValueError):
            return 1
        return value if value > 0 else 1


@dataclass(frozen=True)
class LlmRoute:
    service: str
    group: str
    url: PlanField
    api_key: Optional[PlanField] = None
    model: str = ""
    api_format: str = ""
    provider_name: str = ""


@dataclass(frozen=True)
class GenericValue:
    field: str
    source_relpath: str
    location: FieldLocation
    original_value: str
    placeholder: str
    value_type: str


@dataclass(frozen=True)
class DeepScanFinding:
    value: str
    source: str
    field: str = ""
    value_type: str = "value"


@dataclass(frozen=True)
class DeepScanFindingsInput:
    generic: tuple[DeepScanFinding, ...] = ()


@dataclass(frozen=True)
class ReviewedScanBuildInput:
    url_proxy_pairs: tuple[LlmRoute, ...]
    generic_values: tuple[GenericValue, ...]


@dataclass(frozen=True)
class ScanContext:
    staging_root: Path
    process_env: Mapping[str, str]
    stage_plan: Any = None
    user_home: Optional[Path] = None


class RuntimeContract(ABC):
    def os_fallback_environment_names(self) -> frozenset[str]:
        return frozenset()

    @abstractmethod
    def routes(self, ctx: ScanContext) -> list[LlmRoute]:
        pass


def build_placeholder(
    service: str,
    source: str,
    field: str = "",
    locator: str = "",
    value_type: str = "",
) -> str:
    seed = "\n".join(part.strip() for part in (service, source, field, locator, value_type))
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest().upper()[:10]
    return f"PLATFORM_MANAGED_VALUE_{digest}"


def build_llm_route(
    *,
    service: str,
    group: str,
    url: str,
    url_field: str,
    source_relpath: str,
    model: str,
    api_format: str,
    provider_name: str = "",
    api_key_field: str = "",
    source_kind: SourceKind = SourceKind.FILE,
    location: Optional[FieldLocation] = None,
) -> LlmRoute:
    normalized_url = str(url or "").strip()
    normalized_api_format = str(api_format or "").strip()
    if not normalized_url or not normalized_api_format:
        raise ValueError("LLM route requires a non-empty URL and api_format")
    api_key = None
    normalized_api_key_field = str(api_key_field or "").strip()
    if normalized_api_key_field:
        api_key = PlanField(
            field=normalized_api_key_field,
            service=service,
            source_kind=source_kind,
            source_relpath=source_relpath,
            location=location,
            original_value="",
            placeholder=build_placeholder(
                service,
                source_relpath,
                field=normalized_api_key_field,
                locator=normalized_url,
                value_type="api_key",
            ),
        )
    return LlmRoute(
        service=service,
        group=group,
        url=PlanField(
            field=url_field,
            service=service,
            source_kind=source_kind,
            source_relpath=source_relpath,
            location=location,
            original_value=normalized_url,
            placeholder=build_placeholder(
                service,
                source_relpath,
                field=url_field,
                locator=normalized_url,
                value_type="url",
            ),
            reviewed_source=source_relpath,
        ),
        api_key=api_key,
        model=str(model or "").strip(),
        api_format=normalized_api_format,
        provider_name=str(provider_name or "").strip(),
    )


@dataclass(frozen=True)
class TargetDescriptor:
    target_id: str
    profile_env_id: Optional[str] = None
    runtime_generation: Optional[str] = None

@dataclass(frozen=True)
class RuntimeAdapter:
    runtime_id: str
    descriptors: tuple[TargetDescriptor, ...]
    target_factory: Callable[[dict], "PackagingTarget"]
    provider_runtime_factory: Callable[[], Any]


@runtime_checkable
class PackagingTarget(Protocol):
    def profile_env_id(self) -> Optional[str]:
        ...

    def build_stage_plan(
        self,
        runtime_dir: str,
    ) -> StagePlan:
        ...

    def prepare_runtime_dir(
        self,
        runtime_dir: str,
    ) -> str:
        ...

    def validate_runtime(
        self,
        runtime_root: Path,
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
    "DeepScanFinding",
    "DeepScanFindingsInput",
    "FieldLocation",
    "GenericValue",
    "LlmRoute",
    "build_placeholder",
    "build_llm_route",
    "PackagingTarget",
    "PROCESS_ENV_SOURCE",
    "PlanField",
    "ReviewedScanBuildInput",
    "RuntimeAdapter",
    "RuntimeContract",
    "ScanContext",
    "SourceKind",
    "TargetDescriptor",
    "call_optional_target_hook",
]
