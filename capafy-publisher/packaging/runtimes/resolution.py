from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from packaging._shared.runtimes.contracts import TargetDescriptor
from packaging._shared.runtimes.support import collect_optional_command_first_line
from packaging._shared.runtimes.version import (
    OPENCLAW_MODERN_MIN_VERSION,
    extract_version,
    version_tuple,
)


OPENCLAW_LEGACY_TARGET = "openclaw_legacy_native"
OPENCLAW_MODERN_TARGET = "openclaw_bundle_aware"


@dataclass(frozen=True)
class TargetResolution:
    requested_name: str
    resolved_name: str
    runtime_generation: str | None = None
    runtime_version: str | None = None
    runtime_version_source: str | None = None


@dataclass(frozen=True)
class TargetResolutionRule:
    resolution_strategy: str = "identity"
    resolution_target_id: str | None = None
    runtime_validation_target_id: str | None = None
    runtime_validation_reported_name: str | None = None


def _target_descriptor(name: str) -> TargetDescriptor:
    from packaging.runtimes.registry import get_target_descriptor as _get_target_descriptor

    return _get_target_descriptor(name)


def get_target_resolution_rule(name: str) -> TargetResolutionRule:
    descriptor = _target_descriptor(name)
    rules = {
        "openclaw": TargetResolutionRule(
            resolution_strategy="openclaw_version",
            runtime_validation_target_id=OPENCLAW_MODERN_TARGET,
            runtime_validation_reported_name="openclaw",
        ),
    }
    return rules.get(descriptor.target_id, TargetResolutionRule())


def _read_json(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _lookup_openclaw_config_version(path: Path) -> str | None:
    payload = _read_json(path)
    if payload is None:
        return None
    candidates = (
        payload.get("meta", {}).get("lastTouchedVersion") if isinstance(payload.get("meta"), dict) else None,
        payload.get("wizard", {}).get("lastRunVersion") if isinstance(payload.get("wizard"), dict) else None,
        payload.get("version"),
    )
    for item in candidates:
        version = extract_version(str(item)) if item is not None else None
        if version:
            return version
    return None


def _resolve_openclaw_config_path(home: Path | None = None) -> Path:
    if home is not None:
        return (home.expanduser() / ".openclaw" / "openclaw.json").resolve()
    from packaging.configure.runtimes.openclaw import target as openclaw_target

    return (openclaw_target.OPENCLAW_ROOT / "openclaw.json").expanduser().resolve()


def detect_openclaw_target_resolution(*, home: Path | None = None) -> TargetResolution:
    config_path = _resolve_openclaw_config_path(home)
    config_version = _lookup_openclaw_config_version(config_path) if config_path.is_file() else None
    cli_line = collect_optional_command_first_line(["openclaw", "--version"])
    cli_version = extract_version(cli_line)

    effective_version = cli_version or config_version
    effective_source = "openclaw --version" if cli_version else str(config_path)
    if effective_version:
        runtime_version_tuple = version_tuple(effective_version)
        resolved_name = OPENCLAW_MODERN_TARGET
        if runtime_version_tuple is not None and runtime_version_tuple < OPENCLAW_MODERN_MIN_VERSION:
            resolved_name = OPENCLAW_LEGACY_TARGET
        return TargetResolution(
            requested_name="openclaw",
            resolved_name=resolved_name,
            runtime_generation=resolved_name,
            runtime_version=effective_version,
            runtime_version_source=effective_source,
        )

    return TargetResolution(
        requested_name="openclaw",
        resolved_name=OPENCLAW_LEGACY_TARGET,
        runtime_generation=OPENCLAW_LEGACY_TARGET,
        runtime_version=None,
        runtime_version_source="default",
    )


def _resolve_static_target(
    requested_name: str,
    descriptor: TargetDescriptor,
    resolution_rule: TargetResolutionRule,
) -> TargetResolution:
    resolved_name = resolution_rule.resolution_target_id or descriptor.target_id
    resolved_descriptor = descriptor if resolved_name == descriptor.target_id else _target_descriptor(resolved_name)
    runtime_generation = descriptor.runtime_generation or resolved_descriptor.runtime_generation
    return TargetResolution(
        requested_name=requested_name,
        resolved_name=resolved_name,
        runtime_generation=runtime_generation,
    )


def resolve_target_request(requested_name: str, *, home: Path | None = None) -> TargetResolution:
    normalized = requested_name.strip()
    descriptor = _target_descriptor(normalized)
    resolution_rule = get_target_resolution_rule(normalized)
    if resolution_rule.resolution_strategy == "openclaw_version":
        return detect_openclaw_target_resolution(home=home)
    return _resolve_static_target(normalized, descriptor, resolution_rule)


def resolve_target_name(requested_name: str, *, home: Path | None = None) -> str:
    return resolve_target_request(requested_name, home=home).resolved_name


def resolve_runtime_validation_target(requested_name: str | None) -> tuple[str, str]:
    normalized = (requested_name or "").strip() or "openclaw"
    resolution_rule = get_target_resolution_rule(normalized)
    if resolution_rule.runtime_validation_target_id:
        reported_name = resolution_rule.runtime_validation_reported_name or normalized
        return resolution_rule.runtime_validation_target_id, reported_name
    resolution = resolve_target_request(normalized)
    reported_name = resolution_rule.runtime_validation_reported_name or resolution.resolved_name
    return resolution.resolved_name, reported_name


def build_runtime_metadata(env_id: str, *, home: Path | None = None) -> dict[str, str]:
    resolution = resolve_target_request(env_id, home=home)
    payload = {"resolved_target": resolution.resolved_name}
    if resolution.runtime_generation:
        payload["runtime_generation"] = resolution.runtime_generation
    if resolution.runtime_version:
        payload["runtime_version"] = resolution.runtime_version
    if resolution.runtime_version_source:
        payload["runtime_version_source"] = resolution.runtime_version_source
    return payload


__all__ = [
    "OPENCLAW_LEGACY_TARGET",
    "OPENCLAW_MODERN_MIN_VERSION",
    "OPENCLAW_MODERN_TARGET",
    "TargetResolutionRule",
    "TargetResolution",
    "build_runtime_metadata",
    "detect_openclaw_target_resolution",
    "get_target_resolution_rule",
    "resolve_runtime_validation_target",
    "resolve_target_name",
    "resolve_target_request",
]
