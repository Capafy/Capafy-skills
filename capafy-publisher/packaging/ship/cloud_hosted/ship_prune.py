from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packaging.configure.staging.review import refresh_reviewed_scan_metadata
from packaging.configure.staging.review_confirmation import reconcile_reviewed_scan_with_platform_confirmation
from packaging._shared.reviewed_scan.io import persist_reviewed_scan
from packaging.configure.scan.staging_scan import scan_staging_full
from packaging.ship.cloud_hosted.effective_scan import EffectiveScanGroups
from packaging.configure.url_proxy.orchestrator import is_runtime_applicable
from packaging.configure.url_proxy.runtime_registry import BUILTIN_RUNTIMES


@dataclass(frozen=True)
class ShipPruneResult:
    reviewed_scan: dict[str, Any]
    effective_scan: EffectiveScanGroups
    provider_summary: dict[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.provider_summary is None:
            object.__setattr__(self, "provider_summary", {})


def _apply_platform_confirmed_provider_selection(
    *,
    staging_root: Path,
    env_id: str,
    reviewed_scan: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(reviewed_scan, dict):
        return {}
    summary: dict[str, Any] = {}
    for runtime in BUILTIN_RUNTIMES:
        if not is_runtime_applicable(runtime, env_id):
            continue
        result = runtime.rewrite_confirmed(staging_root, reviewed_scan)
        if result:
            summary.update(result)
    return summary


def _apply_confirmed_platform_configuration(
    *,
    staging_root: Path,
    env_id: str,
    agent_type: str,
    reviewed_scan: dict[str, Any],
    required_credentials_payload: dict[str, Any] | object,
    developer_work_dir_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(reviewed_scan, dict) or not isinstance(required_credentials_payload, dict):
        return reviewed_scan, {}
    if not required_credentials_payload or not str(staging_root or "").strip() or not staging_root.is_dir():
        return reviewed_scan, {}

    reconciled = reconcile_reviewed_scan_with_platform_confirmation(
        reviewed_scan,
        required_credentials_payload=required_credentials_payload,
    )
    if not isinstance(reconciled, dict):
        return reviewed_scan, {}

    provider_summary = _apply_platform_confirmed_provider_selection(
        staging_root=staging_root,
        env_id=env_id,
        reviewed_scan=reconciled,
    )
    if any(provider_summary.values()):
        raw_scan = scan_staging_full(
            staging_root,
            target_name=env_id,
            platform_agent_type=agent_type,
        ).raw_scan
        refreshed = refresh_reviewed_scan_metadata(
            reconciled,
            raw_scan=raw_scan,
            staging_root=staging_root,
            env_id=env_id,
            agent_type=agent_type,
        )
    elif reconciled != reviewed_scan:
        refreshed = refresh_reviewed_scan_metadata(reconciled)
    else:
        return reviewed_scan, {}

    updated_reviewed_scan = refreshed if isinstance(refreshed, dict) else reconciled
    persist_reviewed_scan(updated_reviewed_scan, developer_work_dir_path=developer_work_dir_path)
    return updated_reviewed_scan, provider_summary


def prune_cloud_hosted_reviewed_scan(
    *,
    env_id: str = "",
    agent_type: str,
    reviewed_scan: dict[str, Any],
    staging_root: str = "",
    required_credentials_payload: dict[str, Any] | object = None,
    developer_work_dir_path: Path | None = None,
) -> tuple[ShipPruneResult | dict[str, Any], int]:
    provider_summary: dict[str, Any] = {}


    if (
        staging_root
        and isinstance(required_credentials_payload, dict)
        and required_credentials_payload
        and developer_work_dir_path is not None
    ):
        reviewed_scan, provider_summary = _apply_confirmed_platform_configuration(
            staging_root=Path(staging_root),
            env_id=env_id,
            agent_type=agent_type,
            reviewed_scan=reviewed_scan,
            required_credentials_payload=required_credentials_payload,
            developer_work_dir_path=developer_work_dir_path,
        )

    effective_scan = EffectiveScanGroups.from_reviewed_scan(reviewed_scan)
    return ShipPruneResult(
        reviewed_scan=reviewed_scan,
        effective_scan=effective_scan,
        provider_summary=provider_summary,
    ), 0


__all__ = ["ShipPruneResult", "prune_cloud_hosted_reviewed_scan"]
