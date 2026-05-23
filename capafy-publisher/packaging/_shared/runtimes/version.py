from __future__ import annotations

import re



OPENCLAW_MODERN_MIN_VERSION = (2026, 3, 22)

OPENCLAW_VERSION_PATTERN = re.compile(r"(\d{4}\.\d+\.\d+)")


def extract_version(raw_value: str | None) -> str | None:
    if not raw_value:
        return None
    match = OPENCLAW_VERSION_PATTERN.search(raw_value)
    if match:
        return match.group(1)
    stripped = raw_value.strip().lstrip("vV")
    return stripped or None


def version_tuple(version: str | None) -> tuple[int, ...] | None:
    normalized = extract_version(version)
    if not normalized:
        return None
    try:
        return tuple(int(part) for part in normalized.split("."))
    except ValueError:
        return None


__all__ = [
    "OPENCLAW_MODERN_MIN_VERSION",
    "OPENCLAW_VERSION_PATTERN",
    "extract_version",
    "version_tuple",
]
