from __future__ import annotations

from typing import Any

from packaging._shared.contracts.reviewed_scan import credential_counts


def build_deep_scan_payload(
    *,
    agent_id: str,
    agent_version_id: str,
    env_id: str,
    agent_type: str,
    staging_root: str,
    reviewed_scan_path: str,
    reviewed_scan: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": "needs_deep_scan",
        "agent_id": agent_id,
        "agent_version_id": agent_version_id,
        "env_id": env_id,
        "agent_type": agent_type,
        "staging_path": staging_root,
        "reviewed_scan_path": reviewed_scan_path,
        "credential_counts": credential_counts(reviewed_scan),
        "next_step": "llm_deep_scan_then_rerun_publish_configure_without_deep_scan",
        "developer_next_steps": [
            "Use staging_path as the source boundary for LLM deep scan.",
            "Rule-matched generic values have already been rewritten to platform-managed placeholders before this deep scan.",
            "Treat _scan_only files as audit context only; do not report values from them as generic findings.",
            "Look only for missed credential-like secrets/sensitive values; do not discover new url_proxy entries.",
            'Write findings as a JSON object with generic and env_var arrays: {"generic": [], "env_var": []}.',
            "generic items need non-empty value and source fields.",
            "env_var items need non-empty value and field (env var name).",
            "Keep generic file secrets in generic and env vars in env_var.",
            "Do not edit reviewed-scan.json or hand-write bucket entries.",
            "If deep scan finds missed sensitive data, rerun publish-configure with --deep-scan-findings-file <path> so the normal pipeline can validate, infer fields, rewrite placeholders, and regenerate reviewed-scan.",
            "If no missed sensitive data is found, rerun publish-configure without --deep-scan to continue.",
        ],
    }


__all__ = [
    "build_deep_scan_payload",
]
