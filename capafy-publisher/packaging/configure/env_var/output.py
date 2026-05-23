from __future__ import annotations

from packaging._shared.contracts.reviewed_scan import build_reviewed_env_var_item


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
    excluded_fields: set[str] | None = None,
) -> list[dict]:
    normalized_excluded_fields = {
        str(field or "").strip()
        for field in (excluded_fields or set())
        if str(field or "").strip()
    }
    seen: dict[str, dict] = {}
    for candidate in process_env_candidates:
        env_name = candidate.get("env_name", "")
        field = str(candidate.get("field") or env_name).strip()
        if field.lower() in _INFRASTRUCTURE_ENV_NAMES:
            continue
        if field in normalized_excluded_fields:
            continue
        value = candidate["value"]
        if value in seen:
            continue
        seen[value] = build_reviewed_env_var_item(
            field=field,
            value=value,
            use=f"Environment variable {field}" if field else "Environment variable",
        )

    return list(seen.values())


__all__ = ["build_env_vars_output"]
