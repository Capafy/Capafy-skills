from __future__ import annotations
from typing import Optional

import json
import os
from pathlib import Path
import subprocess
import time


TIMEZONE_HEADER = "X-Timezone"
APP_VERSION_HEADER = "X-App-Version"
DEFAULT_TIMEZONE = "UTC"

WINDOWS_TZ_TO_IANA = {
    "UTC": "UTC",
    "GMT Standard Time": "Europe/London",
    "W. Europe Standard Time": "Europe/Berlin",
    "Central Europe Standard Time": "Europe/Budapest",
    "Romance Standard Time": "Europe/Paris",
    "Russian Standard Time": "Europe/Moscow",
    "Pacific Standard Time": "America/Los_Angeles",
    "Mountain Standard Time": "America/Denver",
    "Central Standard Time": "America/Chicago",
    "Eastern Standard Time": "America/New_York",
    "Atlantic Standard Time": "America/Halifax",
    "China Standard Time": "Asia/Shanghai",
    "Tokyo Standard Time": "Asia/Tokyo",
    "Korea Standard Time": "Asia/Seoul",
    "Singapore Standard Time": "Asia/Singapore",
    "India Standard Time": "Asia/Kolkata",
    "AUS Eastern Standard Time": "Australia/Sydney",
    "New Zealand Standard Time": "Pacific/Auckland",
}

_APP_VERSION_CACHE: Optional[str] = None
_SKILL_DIR = Path(__file__).resolve().parents[1]


def skill_dir() -> Path:
    return _SKILL_DIR


def load_app_version(
    *,
    skill_dir_override: Optional[Path] = None,
    skill_dir: Optional[Path] = None,
) -> str:
    global _APP_VERSION_CACHE
    root_override = skill_dir_override or skill_dir
    if root_override is None and _APP_VERSION_CACHE is not None:
        return _APP_VERSION_CACHE
    root = root_override or _SKILL_DIR
    index_path = root / "api-docs" / "index.json"
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        version = ""
    else:
        version = str(payload.get("version", "")).strip() if isinstance(payload, dict) else ""
    if root_override is None:
        _APP_VERSION_CACHE = version
    return version


def _normalize_timezone_candidate(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        return ""
    if candidate.startswith(":"):
        candidate = candidate[1:].strip()
    if not candidate:
        return ""
    if candidate.startswith("/"):
        marker = "/zoneinfo/"
        if marker in candidate:
            candidate = candidate.split(marker, 1)[1]
        else:
            return ""
    if candidate in {".", "localtime"}:
        return ""
    return candidate


def _read_etc_timezone() -> str:
    try:
        return Path("/etc/timezone").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _timezone_from_localtime_symlink() -> str:
    localtime = Path("/etc/localtime")
    try:
        if not localtime.is_symlink():
            return ""
        resolved = str(localtime.resolve())
    except OSError:
        return ""
    marker = "/zoneinfo/"
    if marker not in resolved:
        return ""
    return _normalize_timezone_candidate(resolved.split(marker, 1)[1])


def _timezone_from_windows_tzutil() -> str:
    try:
        completed = subprocess.run(
            ["tzutil", "/g"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if completed.returncode != 0:
        return ""
    windows_name = completed.stdout.strip()
    if not windows_name:
        return ""
    return WINDOWS_TZ_TO_IANA.get(windows_name, windows_name)


def local_timezone_name() -> str:
    for candidate in (
        os.environ.get("TZ", ""),
        _read_etc_timezone(),
        _timezone_from_localtime_symlink(),
        _timezone_from_windows_tzutil(),
    ):
        normalized = _normalize_timezone_candidate(str(candidate))
        if normalized:
            return normalized
    fallback = time.tzname[0] if time.tzname else ""
    return _normalize_timezone_candidate(fallback) or DEFAULT_TIMEZONE


def platform_context_headers() -> dict[str, str]:
    headers = {TIMEZONE_HEADER: local_timezone_name()}
    version = load_app_version()
    if version:
        headers[APP_VERSION_HEADER] = version
    return headers


__all__ = [
    "APP_VERSION_HEADER",
    "DEFAULT_TIMEZONE",
    "TIMEZONE_HEADER",
    "load_app_version",
    "local_timezone_name",
    "platform_context_headers",
    "skill_dir",
]
