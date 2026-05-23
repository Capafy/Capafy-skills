from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from packaging.configure.contracts import FieldLocation, SourceKind


@dataclass(frozen=True)
class Candidate:
    role: Literal["api_key", "base_url", "url_proxy_group", "synthesized_api_key"]
    field: str
    value: str
    source_kind: SourceKind
    source_relpath: str
    location: FieldLocation | None = None
    extra: dict[str, Any] = field(default_factory=dict)


__all__ = ["Candidate"]
