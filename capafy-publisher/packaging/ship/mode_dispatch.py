from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from packaging._shared.contracts.publish_work_state import (
    STAGE_BUNDLE_PREPARED,
    STAGE_CONFIG_SUBMITTED,
)
from packaging._shared.mode_dispatch import lookup_mode
from packaging.ship.contexts import (
    ArtifactPackageContext,
    ArtifactValidateContext,
    PackageContext,
    ValidateContext,
)

from packaging.ship.buyout.package import (
    build_buyout_artifact_package_payload,
    build_buyout_validate_reviewed_scan_json,
    package_buyout_staging,
)
from packaging.ship.buyout.validate import (
    build_buyout_validation_payload,
    load_buyout_reviewed_scan_payload as load_buyout_validate_reviewed_scan,
)
from packaging.ship.cloud_hosted.package import (
    build_cloud_hosted_artifact_package_payload,
    build_cloud_hosted_validate_reviewed_scan_json,
    package_cloud_hosted_staging,
)
from packaging.ship.cloud_hosted.validate import (
    build_cloud_hosted_validation_payload,
    load_cloud_hosted_reviewed_scan_payload as load_cloud_hosted_validate_reviewed_scan,
)


def _package_cloud_hosted(ctx: PackageContext) -> Dict[str, Any]:
    return package_cloud_hosted_staging(
        staging_root=ctx.staging_root,
        package_json=ctx.package_json,
        output_path=ctx.output_path,
        cleanup_staging=ctx.cleanup_staging,
    )


def _package_buyout(ctx: PackageContext) -> Dict[str, Any]:
    return package_buyout_staging(
        staging_root=ctx.staging_root,
        package_json=ctx.package_json,
        output_path=ctx.output_path,
        cleanup_staging=ctx.cleanup_staging,
    )


def _validate_cloud_hosted(ctx: ValidateContext) -> Dict[str, Any]:
    reviewed_scan_payload = load_cloud_hosted_validate_reviewed_scan(
        reviewed_scan_json=ctx.reviewed_scan_json,
        reviewed_scan_file=ctx.reviewed_scan_file,
    )
    return build_cloud_hosted_validation_payload(
        runtime_root=ctx.runtime_root,
        target=ctx.target,
        expected_version=ctx.expected_version,
        reviewed_scan_payload=reviewed_scan_payload,
    )


def _validate_buyout(ctx: ValidateContext) -> Dict[str, Any]:
    reviewed_scan_payload = load_buyout_validate_reviewed_scan(
        reviewed_scan_json=ctx.reviewed_scan_json,
        reviewed_scan_file=ctx.reviewed_scan_file,
    )
    return build_buyout_validation_payload(
        runtime_root=ctx.runtime_root,
        resolved_target_name=ctx.resolved_target_name,
        reviewed_scan_payload=reviewed_scan_payload,
    )


def _artifact_package_cloud_hosted(ctx: ArtifactPackageContext) -> Dict[str, Any]:
    return build_cloud_hosted_artifact_package_payload(effective_scan_payload=ctx.effective_scan_payload)


def _artifact_package_buyout(ctx: ArtifactPackageContext) -> Dict[str, Any]:
    return build_buyout_artifact_package_payload(effective_scan_payload=ctx.effective_scan_payload)


def _artifact_validate_cloud_hosted(ctx: ArtifactValidateContext) -> Optional[str]:
    return build_cloud_hosted_validate_reviewed_scan_json(effective_scan_payload=ctx.effective_scan_payload)


def _artifact_validate_buyout(ctx: ArtifactValidateContext) -> Optional[str]:
    return build_buyout_validate_reviewed_scan_json(effective_scan_payload=ctx.effective_scan_payload)


@dataclass(frozen=True)
class ShipMode:
    name: str
    biz_type: str
    requires_config_keys_gate: bool
    ship_required_stage: str
    package: Callable[[PackageContext], Dict[str, Any]]
    validate: Callable[[ValidateContext], Dict[str, Any]]
    artifact_package_payload: Callable[[ArtifactPackageContext], Dict[str, Any]]
    artifact_validate_reviewed_scan_json: Callable[[ArtifactValidateContext], Optional[str]]


CLOUD_HOSTED = ShipMode(
    name="run_online",
    biz_type="run_online",
    requires_config_keys_gate=True,
    ship_required_stage=STAGE_CONFIG_SUBMITTED,
    package=_package_cloud_hosted,
    validate=_validate_cloud_hosted,
    artifact_package_payload=_artifact_package_cloud_hosted,
    artifact_validate_reviewed_scan_json=_artifact_validate_cloud_hosted,
)

BUYOUT = ShipMode(
    name="download",
    biz_type="download",
    requires_config_keys_gate=False,
    ship_required_stage=STAGE_BUNDLE_PREPARED,
    package=_package_buyout,
    validate=_validate_buyout,
    artifact_package_payload=_artifact_package_buyout,
    artifact_validate_reviewed_scan_json=_artifact_validate_buyout,
)

_REGISTRY: Dict[str, ShipMode] = {
    "run_online": CLOUD_HOSTED,
    "download": BUYOUT,
}


def get_ship_mode(agent_type: str) -> ShipMode:
    return lookup_mode(_REGISTRY, agent_type)


__all__ = [
    "ArtifactPackageContext",
    "ArtifactValidateContext",
    "BUYOUT",
    "CLOUD_HOSTED",
    "PackageContext",
    "ShipMode",
    "ValidateContext",
    "get_ship_mode",
]
