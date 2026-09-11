from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from packaging.common.home import safe_expanduser_path
from packaging.runtime.registry import get_target_descriptor
from packaging.runtime.support import collect_optional_command_first_line


OPENCLAW_MIN_VERSION = (2026, 3, 22)
OPENCLAW_VERSION_PATTERN = re.compile(r"(\d{4}\.\d+\.\d+)")


def _extract_version(raw_value: Optional[str]) -> Optional[str]:
    if not raw_value:
        return None
    match = OPENCLAW_VERSION_PATTERN.search(raw_value)
    if match:
        return match.group(1)
    stripped = raw_value.strip().lstrip("vV")
    return stripped or None


def _version_tuple(version: Optional[str]) -> Optional[tuple[int, ...]]:
    normalized = _extract_version(version)
    if not normalized:
        return None
    try:
        return tuple(int(part) for part in normalized.split("."))
    except ValueError:
        return None


@dataclass(frozen=True)
class TargetResolution:
    resolved_name: str
    runtime_generation: Optional[str] = None
    runtime_version: Optional[str] = None
    runtime_version_source: Optional[str] = None


def _read_json(path: Path) -> Optional[dict]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _valid_openclaw_version(raw_value: object) -> Optional[str]:
    version = _extract_version(str(raw_value)) if raw_value is not None else None
    parts = _version_tuple(version)
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

    effective_parts = _version_tuple(effective_version)
    if effective_parts is None or effective_parts < OPENCLAW_MIN_VERSION:
        raise ValueError(
            f"unsupported OpenClaw version {effective_version}; "
            "version 2026.3.22 or newer is required"
        )

    return TargetResolution(
        resolved_name="openclaw",
        runtime_version=effective_version,
        runtime_version_source="openclaw --version" if cli_version else str(config_path),
    )


def resolve_target_request(requested_name: str) -> TargetResolution:
    normalized = requested_name.strip()
    descriptor = get_target_descriptor(normalized)
    return TargetResolution(
        resolved_name=descriptor.target_id,
        runtime_generation=descriptor.runtime_generation,
    )


def resolve_target_name(requested_name: str) -> str:
    return resolve_target_request(requested_name).resolved_name


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
    "resolve_target_name",
    "resolve_target_request",
]
