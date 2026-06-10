from __future__ import annotations

from typing import Any

from packaging._shared.contracts.reviewed_scan import credential_counts
from packaging._shared.common.cli import build_soft_action
from packaging.configure.staging.source_boundary import deep_scan_file_boundary


def _redacted_url_hint(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "://" not in text:
        return ""
    scheme, rest = text.split("://", 1)
    host = rest.split("/", 1)[0]
    if not host:
        return f"{scheme}://..."
    return f"{scheme}://{host}/..."


def _credential_url_proxy_hints(reviewed_scan: dict[str, Any]) -> list[dict[str, str]]:
    hints: list[dict[str, str]] = []
    url_proxy_items = reviewed_scan.get("url_proxy", [])
    if not isinstance(url_proxy_items, list):
        return hints
    for item in url_proxy_items:
        if not isinstance(item, dict):
            continue
        api_key = item.get("api_key")
        url = item.get("url")
        if not isinstance(api_key, dict) or not isinstance(url, dict):
            continue
        hint = {
            "api_key_field": str(api_key.get("field", "") or "").strip(),
            "url_field": str(url.get("field", "") or "").strip(),
            "url_hint": _redacted_url_hint(url.get("url") or url.get("value")),
            "source": str(url.get("source") or api_key.get("source") or "").strip(),
            "url_proxy_group": str(item.get("url_proxy_group", "") or "").strip(),
        }
        hints.append({key: value for key, value in hint.items() if value})
    return hints


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
    file_boundary = deep_scan_file_boundary(
        staging_root=staging_root,
        excluded_relpaths=(
            str(item.get("source", "") or item.get("path", "")).strip()
            for item in reviewed_scan.get("excludes", [])
            if isinstance(item, dict)
        ),
        agent_type=agent_type,
    )
    return build_soft_action(
        status="needs_deep_scan",
        action_type="llm_deep_scan",
        next_step="llm_deep_scan_then_rerun_publish_configure_without_deep_scan",
        developer_next_steps=[
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
        agent_id=agent_id,
        agent_version_id=agent_version_id,
        env_id=env_id,
        agent_type=agent_type,
        staging_path=staging_root,
        reviewed_scan_path=reviewed_scan_path,
        credential_counts=credential_counts(reviewed_scan),
        credential_hints={
            "url_proxy": _credential_url_proxy_hints(reviewed_scan),
        },
        scan_files=file_boundary["scan_files"],
        scan_files_summary=file_boundary["scan_files_summary"],
    )


__all__ = [
    "build_deep_scan_payload",
]
