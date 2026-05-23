from __future__ import annotations

from typing import Any

from packaging._shared.contracts.reviewed_scan import required_list, sanitize_reviewed_scan_payload


def build_cloud_hosted_scan_payload(
    scan_payload: dict[str, Any],
    *,
    label: str = "effective_scan_payload",
) -> dict[str, Any]:
    sanitized = sanitize_reviewed_scan_payload(scan_payload)
    return {
        "agent_type": "run_online",
        "url_proxy": required_list(sanitized, "url_proxy", label=label),
        "generic": required_list(sanitized, "generic", label=label),
        "env_var": required_list(sanitized, "env_var", label=label),
        "excludes": required_list(sanitized, "excludes", label=label),
    }


__all__ = [
    "build_cloud_hosted_scan_payload",
]
