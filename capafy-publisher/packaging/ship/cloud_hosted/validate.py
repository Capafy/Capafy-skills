from __future__ import annotations

from pathlib import Path
from typing import NamedTuple, Optional

from packaging._shared.common.fs import normalize_path
from packaging._shared.contracts.reviewed_scan import load_reviewed_scan_payload, normalize_reviewed_scan_payload


class CloudHostedValidationScan(NamedTuple):
    deploy_items_count: int
    source: str


def load_cloud_hosted_reviewed_scan_payload(
    *,
    reviewed_scan_json: Optional[str] = None,
    reviewed_scan_file: Optional[str] = None,
) -> Optional[CloudHostedValidationScan]:
    if reviewed_scan_json and reviewed_scan_file:
        raise ValueError("--reviewed-scan-json and --reviewed-scan-file cannot be passed together")

    payload_source = ""
    if reviewed_scan_json:
        payload = load_reviewed_scan_payload(reviewed_scan_json, label="reviewed_scan_json")
        payload_source = "reviewed_scan_json"
    elif reviewed_scan_file:
        reviewed_scan_path = normalize_path(reviewed_scan_file)
        if not reviewed_scan_path.is_file():
            raise ValueError(f"reviewed_scan_file does not exist: {reviewed_scan_path}")
        payload = load_reviewed_scan_payload(
            reviewed_scan_path.read_text(encoding="utf-8"),
            label="reviewed_scan_file",
        )
        payload_source = "reviewed_scan_file"
    else:
        return None

    key_items, runtime_values = normalize_reviewed_scan_payload(payload, label=payload_source)
    return CloudHostedValidationScan(
        deploy_items_count=len(key_items) + len(runtime_values),
        source=payload_source,
    )


def _load_validation_inputs(
    *,
    reviewed_scan_payload: Optional[CloudHostedValidationScan] = None,
) -> CloudHostedValidationScan:
    if reviewed_scan_payload is not None:
        return reviewed_scan_payload

    raise ValueError("cloud_hosted validate-runtime requires --reviewed-scan-file or --reviewed-scan-json")


def validate_cloud_hosted_runtime(
    runtime_root: Path,
    *,
    target,
    expected_version: Optional[str] = None,
    reviewed_scan_payload: Optional[CloudHostedValidationScan] = None,
) -> dict:
    validation_scan = _load_validation_inputs(
        reviewed_scan_payload=reviewed_scan_payload,
    )
    validation_result = target.validate_runtime(runtime_root, expected_version=expected_version)
    warnings = validation_result.get("warnings")
    normalized_warnings = [str(item) for item in warnings if str(item).strip()] if isinstance(warnings, list) else []
    return {
        "platform_managed_validation": True,
        "deploy_items_count": validation_scan.deploy_items_count,
        "reviewed_scan_source": validation_scan.source,
        **validation_result,
        "warnings": normalized_warnings,
    }


def build_cloud_hosted_validation_payload(
    *,
    runtime_root: Path,
    target,
    expected_version: Optional[str],
    reviewed_scan_payload: Optional[CloudHostedValidationScan],
) -> dict:
    return validate_cloud_hosted_runtime(
        runtime_root=runtime_root,
        target=target,
        expected_version=expected_version,
        reviewed_scan_payload=reviewed_scan_payload,
    )


__all__ = [
    "CloudHostedValidationScan",
    "build_cloud_hosted_validation_payload",
    "load_cloud_hosted_reviewed_scan_payload",
    "validate_cloud_hosted_runtime",
]
