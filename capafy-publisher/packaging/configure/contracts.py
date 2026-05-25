from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, Optional


class SourceKind(str, Enum):
    FILE = "file"
    PROCESS_ENV = "process_env"
    SYNTHESIZED = "synthesized"



PROCESS_ENV_SOURCE = "process.env"


@dataclass(frozen=True)
class FieldLocation:
    fmt: Literal["dotenv", "json", "toml"]
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
        return ""

    def occurrence_index_identity(self) -> int:
        return self.occurrence_index if self.occurrence_index > 0 else 1

    @classmethod
    def from_source_detail(cls, source_detail: str, *, field: str = "") -> FieldLocation:
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
        if self.location is None:
            return ""
        return self.location.to_source_detail(self.field)

    def occurrence_index_identity(self) -> int:
        try:
            value = int(self.reviewed_occurrence_index)
        except (TypeError, ValueError):
            return 1
        return value if value > 0 else 1


@dataclass(frozen=True)
class UrlProxyPair:
    contract_id: str
    service: str
    group: str
    key: PlanField
    url: PlanField
    is_synthesized: bool
    model: str = ""
    api_format: str = ""


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
class EnvVar:
    name: str
    referenced_in: tuple[str, ...]
    process_value: str
    placeholder: str


@dataclass(frozen=True)
class DeepScanFindingsInput:
    generic: tuple[DeepScanFinding, ...] = ()
    env_var: tuple[EnvVar, ...] = ()


@dataclass(frozen=True)
class ExcludedFile:
    source: str
    reason: str


@dataclass(frozen=True)
class ReviewedScanBuildInput:
    url_proxy_pairs: tuple[UrlProxyPair, ...]
    generic_values: tuple[GenericValue, ...]
    env_vars: tuple[EnvVar, ...]
    excludes: tuple[ExcludedFile, ...]

    def to_reviewed_scan(self, *, review_binding: dict[str, str]) -> dict[str, Any]:
        from packaging.configure.reviewed_scan_builder import build_reviewed_scan_from_input

        return build_reviewed_scan_from_input(self, review_binding=review_binding)

__all__ = [
    "EnvVar",
    "ExcludedFile",
    "FieldLocation",
    "DeepScanFinding",
    "DeepScanFindingsInput",
    "GenericValue",
    "PROCESS_ENV_SOURCE",
    "PlanField",
    "ReviewedScanBuildInput",
    "SourceKind",
    "UrlProxyPair",
]
