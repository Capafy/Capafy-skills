from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packaging.configure.contracts import GenericValue
from packaging.configure.generic_keys import filter_generic_values


@dataclass(frozen=True)
class GeneralScanResult:
    generic_values: tuple[GenericValue, ...]


def run_general_scan(raw_scan: dict[str, Any]) -> GeneralScanResult:
    raw_generic = raw_scan.get("generic", [])
    generic_values = filter_generic_values(raw_generic if isinstance(raw_generic, list) else [])

    return GeneralScanResult(
        generic_values=tuple(generic_values),
    )


__all__ = ["GeneralScanResult", "run_general_scan"]
