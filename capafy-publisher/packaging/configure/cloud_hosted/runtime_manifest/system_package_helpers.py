from __future__ import annotations

import re
import shlex


TABLE_SPLIT_PATTERN = re.compile(r"\s{2,}")


def first_output_line(payload: dict) -> str | None:
    for key in ("stdout", "stderr"):
        value = payload.get(key)
        if value:
            return str(value).splitlines()[0]
    return None


def fallback_os_release_value(raw_value: str) -> str:
    normalized = raw_value.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {"'", '"'}:
        return normalized[1:-1]
    if normalized.startswith(("'", '"')):
        return normalized[1:]
    if normalized.endswith(("'", '"')):
        return normalized[:-1]
    return normalized


def format_command(args: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in args)


def split_table_columns(line: str) -> list[str]:
    return [column.strip() for column in TABLE_SPLIT_PATTERN.split(line.strip()) if column.strip()]


def extract_named_versions(payload: object, versions: dict[str, str] | None = None) -> dict[str, str]:

    if versions is None:
        versions = {}
    if isinstance(payload, dict):
        name: str | None = None
        version: str | None = None
        for key, value in payload.items():
            lowered = str(key).lower()
            if lowered in {"name", "app"} and isinstance(value, str):
                name = value
            elif lowered == "version" and isinstance(value, (str, int, float)):
                version = str(value)
        if name and version:
            versions[name] = version
        for value in payload.values():
            extract_named_versions(value, versions)
    elif isinstance(payload, list):
        for item in payload:
            extract_named_versions(item, versions)
    return versions


__all__ = [
    "TABLE_SPLIT_PATTERN",
    "extract_named_versions",
    "fallback_os_release_value",
    "first_output_line",
    "format_command",
    "split_table_columns",
]
