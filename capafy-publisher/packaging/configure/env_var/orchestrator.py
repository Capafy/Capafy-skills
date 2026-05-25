from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Union

from packaging.configure.contracts import (
    EnvVar,
    ExcludedFile,
    GenericValue,
)
from packaging.configure.env_var import (
    build_env_vars_output,
    collect_process_env_candidates,
)
from packaging.configure.generic_keys import filter_generic_values


@dataclass(frozen=True)
class GeneralScanResult:
    generic_values: tuple[GenericValue, ...]
    env_vars: tuple[EnvVar, ...]
    excludes: tuple[ExcludedFile, ...]


def run_general_scan(
    raw_scan: dict[str, Any],
    *,
    process_env: dict[str, str],
    claimed_process_env_names: frozenset[str],
    referenced_env_names: Union[frozenset[str], set[str]] = frozenset(),
    env_url_hints: Optional[dict[str, str]] = None,
) -> GeneralScanResult:

    raw_generic = raw_scan.get("generic", [])
    generic_values = filter_generic_values(raw_generic if isinstance(raw_generic, list) else [])


    raw_excludes = raw_scan.get("excludes", [])
    existing_excludes = [
        ExcludedFile(
            source=str(item.get("source", "") or item.get("path", "")).strip(),
            reason=str(item.get("reason", "")).strip(),
        )
        for item in raw_excludes
        if isinstance(item, dict) and str(item.get("source", "") or item.get("path", "")).strip()
    ]


    process_env_candidates, _, _ = collect_process_env_candidates(
        process_env,
        set(referenced_env_names),
        env_url_hints or {},
    )
    env_var_items = build_env_vars_output(
        process_env_candidates,
        excluded_fields=set(claimed_process_env_names),
    )
    env_vars = tuple(
        EnvVar(
            name=str(item.get("field", "")).strip(),
            referenced_in=tuple(
                str(x) for x in item.get("referenced_in", []) if str(x).strip()
            ) if isinstance(item.get("referenced_in"), list) else (),
            process_value=str(item.get("value", "")).strip(),
            placeholder=str(item.get("placeholder", "")).strip(),
        )
        for item in env_var_items
        if isinstance(item, dict) and str(item.get("field", "")).strip()
    )

    return GeneralScanResult(
        generic_values=tuple(generic_values),
        env_vars=env_vars,
        excludes=tuple(existing_excludes),
    )


__all__ = ["GeneralScanResult", "run_general_scan"]
