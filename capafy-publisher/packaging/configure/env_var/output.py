from __future__ import annotations
from typing import Optional

from packaging._shared.contracts.reviewed_scan import build_reviewed_env_var_item
from packaging.configure.contracts import PROCESS_ENV_SOURCE


_INFRASTRUCTURE_ENV_NAMES = frozenset(
    {
        "http_proxy",
        "https_proxy",
        "no_proxy",
        "all_proxy",
        "ftp_proxy",
        "socks_proxy",
    }
)


def build_env_vars_output(
    process_env_candidates: list[dict],
    *,
    excluded_fields: Optional[set[str]] = None,
) -> list[dict]:
    normalized_excluded_fields = {
        str(field or "").strip()
        for field in (excluded_fields or set())
        if str(field or "").strip()
    }
    seen: dict[tuple[str, str, str], dict] = {}
    for candidate in process_env_candidates:
        env_name = candidate.get("env_name", "")
        field = str(candidate.get("field") or env_name).strip()
        if field.lower() in _INFRASTRUCTURE_ENV_NAMES:
            continue
        if field in normalized_excluded_fields:
            continue
        value = candidate["value"]
        source = str(candidate.get("source", "") or "").strip()
        referenced_in = [
            str(item).strip()
            for item in candidate.get("referenced_in", [])
            if str(item).strip()
        ] if isinstance(candidate.get("referenced_in"), list) else []
        if source and source != PROCESS_ENV_SOURCE and source not in referenced_in:
            referenced_in.append(source)
        identity = (field, value, source)
        if identity in seen:
            existing_references = seen[identity].setdefault("referenced_in", [])
            if isinstance(existing_references, list):
                for reference in referenced_in:
                    if reference not in existing_references:
                        existing_references.append(reference)
            continue
        seen[identity] = build_reviewed_env_var_item(
            field=field,
            value=value,
            referenced_in=referenced_in,
            use=f"Environment variable {field}" if field else "Environment variable",
        )

    return list(seen.values())


__all__ = ["build_env_vars_output"]
