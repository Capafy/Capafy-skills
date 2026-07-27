from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from packaging._shared.common.home import safe_expanduser_path
from packaging._shared.runtimes.contracts import TargetDescriptor
from packaging._shared.runtimes.support import collect_optional_command_first_line
from packaging._shared.runtimes.version import OPENCLAW_MIN_VERSION, extract_version, version_tuple


@dataclass(frozen=True)
class TargetResolution:
    requested_name: str
    resolved_name: str
    runtime_generation: Optional[str] = None
    runtime_version: Optional[str] = None
    runtime_version_source: Optional[str] = None


def _target_descriptor(name: str) -> TargetDescriptor:
    from packaging.runtimes.registry import get_target_descriptor

    return get_target_descriptor(name)


def _read_json(path: Path) -> Optional[dict]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _valid_openclaw_version(raw_value: object) -> Optional[str]:
    version = extract_version(str(raw_value)) if raw_value is not None else None
    parts = version_tuple(version)
    return version if parts is not None and len(parts) == 3 else None


def _lookup_openclaw_config_version(path: Path) -> Optional[str]:
    payload = _read_json(path)
    if payload is None:
        return None
    candidates = (
        payload.get("meta", {}).get("lastTouchedVersion") if isinstance(payload.get("meta"), dict) else None,
        payload.get("wizard", {}).get("lastRunVersion") if isinstance(payload.get("wizard"), dict) else None,
        payload.get("version"),
    )
    return next((version for item in candidates if (version := _valid_openclaw_version(item))), None)


def _resolve_openclaw_config_path(home: Optional[Path] = None) -> Path:
    if home is not None:
        return (home.expanduser() / ".openclaw" / "openclaw.json").resolve()
    return safe_expanduser_path("~/.openclaw/openclaw.json").resolve()


def detect_openclaw_target_resolution(*, home: Optional[Path] = None) -> TargetResolution:
    config_path = _resolve_openclaw_config_path(home)
    cli_version = _valid_openclaw_version(collect_optional_command_first_line(["openclaw", "--version"]))
    config_version = _lookup_openclaw_config_version(config_path) if config_path.is_file() else None
    effective_version = cli_version or config_version
    if effective_version is None:
        raise ValueError("cannot determine OpenClaw version")

    effective_parts = version_tuple(effective_version)
    if effective_parts is None or effective_parts < OPENCLAW_MIN_VERSION:
        raise ValueError(
            f"unsupported OpenClaw version {effective_version}; "
            "version 2026.3.22 or newer is required"
        )

    return TargetResolution(
        requested_name="openclaw",
        resolved_name="openclaw",
        runtime_version=effective_version,
        runtime_version_source="openclaw --version" if cli_version else str(config_path),
    )


def resolve_target_request(requested_name: str) -> TargetResolution:
    normalized = requested_name.strip()
    descriptor = _target_descriptor(normalized)
    return TargetResolution(
        requested_name=normalized,
        resolved_name=descriptor.target_id,
        runtime_generation=descriptor.runtime_generation,
    )


def resolve_target_name(requested_name: str) -> str:
    return resolve_target_request(requested_name).resolved_name


def resolve_runtime_validation_target(requested_name: Optional[str]) -> tuple[str, str]:
    normalized = (requested_name or "").strip() or "openclaw"
    resolution = resolve_target_request(normalized)
    return resolution.resolved_name, resolution.resolved_name


def build_runtime_metadata(env_id: str, *, home: Optional[Path] = None) -> dict[str, str]:
    normalized = env_id.strip()
    resolution = (
        detect_openclaw_target_resolution(home=home)
        if normalized == "openclaw"
        else resolve_target_request(normalized)
    )
    payload = {"resolved_target": resolution.resolved_name}
    if resolution.runtime_generation:
        payload["runtime_generation"] = resolution.runtime_generation
    if resolution.runtime_version:
        payload["runtime_version"] = resolution.runtime_version
    if resolution.runtime_version_source:
        payload["runtime_version_source"] = resolution.runtime_version_source
    return payload


__all__ = [
    "OPENCLAW_MIN_VERSION",
    "TargetResolution",
    "build_runtime_metadata",
    "detect_openclaw_target_resolution",
    "resolve_runtime_validation_target",
    "resolve_target_name",
    "resolve_target_request",
]
