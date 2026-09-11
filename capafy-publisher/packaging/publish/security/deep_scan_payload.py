from __future__ import annotations

from typing import Any

from packaging.publish.reviewed_scan import credential_counts
from packaging.common.cli import build_soft_action
from packaging.publish.staging.source_boundary import deep_scan_file_boundary


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
        url = item.get("url")
        if not isinstance(url, dict):
            continue
        hint = {
            "url_field": str(url.get("field", "") or "").strip(),
            "url_hint": _redacted_url_hint(url.get("url") or url.get("value")),
            "source": str(url.get("source") or "").strip(),
            "url_proxy_group": str(item.get("url_proxy_group", "") or "").strip(),
            "model": str(item.get("model", "") or "").strip(),
            "api_format": str(item.get("api_format", "") or "").strip(),
            "provider_name": str(item.get("provider_name", "") or "").strip(),
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
    reviewed_scan: dict[str, Any],
) -> dict[str, Any]:
    file_boundary = deep_scan_file_boundary(
        staging_root=staging_root,
        agent_type=agent_type,
    )
    return build_soft_action(
        status="needs_deep_scan",
        action_type="llm_deep_scan",
        next_step="llm_deep_scan_then_rerun_publish_submit_without_deep_scan",
        developer_next_steps=[
            "Inspect every file under staging_path during the LLM deep scan; scan_files lists the complete staging file set.",
            "Only return findings whose source is a reviewable file that will enter the final package.",
            "Treat the rules scan as the existing baseline and return only additional sensitive values found by the deep scan.",
            "Look only for missed credential-like secrets/sensitive values; do not discover new url_proxy entries.",
            'Write findings as a JSON object with a generic array: {"generic": []}.',
            "generic items need non-empty value and source fields.",
            "Do not inspect or return host environment variable values.",
            "Do not hand-write reviewed scan bucket entries.",
            "If deep scan finds missed sensitive data, rerun publish-submit with --deep-scan-findings-file <path> so the normal pipeline can validate the findings and continue the mode-specific replacement or disposition flow.",
            "If no missed sensitive data is found, rerun publish-submit without --deep-scan to continue.",
        ],
        agent_id=agent_id,
        agent_version_id=agent_version_id,
        env_id=env_id,
        agent_type=agent_type,
        staging_path=staging_root,
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
