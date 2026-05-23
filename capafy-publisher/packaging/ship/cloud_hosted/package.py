from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

from packaging.ship.artifacts.archive import build_bundle_archive
from packaging._shared.common.fs import cleanup_staging_root
from packaging._shared.common.constants import WORKSPACE_DOCUMENTS_MANIFEST_NAME
from packaging._shared.contracts.bundle_context import BUNDLE_CONTEXT_NAME
from packaging._shared.contracts.reviewed_scan import (
    CLOUD_HOSTED_URL_PROXY_REQUIRED_MESSAGE,
    load_reviewed_scan_payload,
    normalize_reviewed_scan_payload,
    summarize_reviewed_scan_deploy_items,
)
from packaging._shared.env_profiles import list_profiles, load_profile
from packaging.ship.cloud_hosted.scan_payload import build_cloud_hosted_scan_payload
from packaging._shared.contracts.stage_manifest import STAGE_MANIFEST_NAME
from packaging.ship.artifacts.runtimes.env_runtime_files import collect_required_runtime_paths
from packaging.ship.cloud_hosted.effective_scan import EffectiveScanGroups


def require_cloud_hosted_url_proxy(payload: EffectiveScanGroups) -> EffectiveScanGroups:
    if not isinstance(payload, EffectiveScanGroups):
        raise ValueError("effective_scan_payload must be an EffectiveScanGroups object")
    if not payload.url_proxy:
        raise ValueError(CLOUD_HOSTED_URL_PROXY_REQUIRED_MESSAGE)
    return payload


def build_cloud_hosted_artifact_package_payload(
    *,
    effective_scan_payload: dict,
) -> dict:
    return build_cloud_hosted_scan_payload(effective_scan_payload)


def build_cloud_hosted_validate_reviewed_scan_json(
    *,
    effective_scan_payload: dict,
) -> str | None:
    return json.dumps(effective_scan_payload, ensure_ascii=False)


def _normalize_excluded_relpath(value: object) -> str:
    normalized = str(value or "").strip().replace("\\", "/")
    if not normalized:
        return ""
    normalized = normalized.split("#", 1)[0].strip()
    normalized = PurePosixPath(normalized.rstrip("/")).as_posix()
    if normalized in ("", "."):
        return ""
    return normalized.lstrip("/")


def _excluded_relpaths_from_package_payload(package_payload: dict) -> set[str]:
    excludes = package_payload.get("excludes", [])
    if not isinstance(excludes, list):
        raise ValueError("package_json.excludes must be an array")

    excluded_relpaths: set[str] = set()
    for index, item in enumerate(excludes):
        if not isinstance(item, dict):
            raise ValueError(f"package_json.excludes[{index}] must be an object")
        relpath = _normalize_excluded_relpath(item.get("source") or item.get("path"))
        if relpath:
            excluded_relpaths.add(relpath)
    return excluded_relpaths


def _env_id_from_package_payload(package_payload: dict) -> str:
    candidates: list[object] = [
        package_payload.get("env_id"),
        package_payload.get("resolved_target"),
    ]
    review_metadata = package_payload.get("_review")
    if isinstance(review_metadata, dict):
        candidates.append(review_metadata.get("env_id"))

    for candidate in candidates:
        env_id = str(candidate or "").strip()
        if env_id:
            return env_id
    return ""


def _env_id_from_runtime_manifest(staging_root: Path) -> str:
    manifest_path = staging_root / "agent.runtime_environment.json"
    if not manifest_path.is_file():
        return ""
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""

    for profile in list_profiles():
        runtime_env = profile.get("runtime_env")
        if not isinstance(runtime_env, dict):
            continue
        version_field = str(runtime_env.get("field", "")).strip()
        if version_field and version_field in payload:
            return str(profile.get("env_id", "")).strip()
    return ""


def _required_runtime_relpaths(staging_root: Path, package_payload: dict) -> set[str]:
    env_id = _env_id_from_package_payload(package_payload) or _env_id_from_runtime_manifest(staging_root)
    if not env_id:
        return set()
    try:
        profile = load_profile(env_id)
    except ValueError:
        return set()
    return set(collect_required_runtime_paths(profile))


def _filter_required_runtime_excludes(
    staging_root: Path,
    package_payload: dict,
    excluded_relpaths: set[str],
) -> set[str]:
    required_paths = _required_runtime_relpaths(staging_root, package_payload)
    if not required_paths:
        return set(excluded_relpaths)
    return {path for path in excluded_relpaths if path not in required_paths}


def package_cloud_hosted_staging(
    staging_root: Path,
    package_json: str,
    output_path: Path,
    *,
    cleanup_staging: bool = False,
) -> dict:
    package_payload = load_reviewed_scan_payload(package_json, label="package_json")
    if not isinstance(package_payload, dict):
        raise ValueError("package_json must be an object")

    key_items, runtime_values = normalize_reviewed_scan_payload(package_payload, label="package_json")
    excluded_relpaths = _filter_required_runtime_excludes(
        staging_root,
        package_payload,
        _excluded_relpaths_from_package_payload(package_payload),
    )
    bundle_result = build_bundle_archive(
        staging_root,
        output_path,
        exclude_paths={
            STAGE_MANIFEST_NAME,
            BUNDLE_CONTEXT_NAME,
            WORKSPACE_DOCUMENTS_MANIFEST_NAME,
        } | excluded_relpaths,
        exclude_prefixes=("_scan_only",),
    )

    payload = {
        "agent_type": "run_online",
        "reviewed_scan": summarize_reviewed_scan_deploy_items(key_items, runtime_values),
        "bundle": bundle_result,
    }
    if cleanup_staging:
        payload["cleanup_summary"] = cleanup_staging_root(staging_root)
    return payload
