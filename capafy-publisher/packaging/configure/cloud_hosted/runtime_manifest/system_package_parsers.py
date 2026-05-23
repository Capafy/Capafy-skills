from __future__ import annotations

from packaging.configure.cloud_hosted.runtime_manifest.system_package_helpers import split_table_columns


def parse_brew_version(name: str, result: dict) -> str | None:
    del name
    line = result.get("stdout")
    if not result.get("ok") or not line:
        return None
    parts = str(line).split()
    return parts[1] if len(parts) >= 2 else None


def parse_winget_version(package_id: str, result: dict) -> str | None:
    stdout = result.get("stdout")
    if not result.get("ok") or not stdout:
        return None
    for raw_line in str(stdout).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith(("name ", "found ", "the following ", "no installed package", "no package")):
            continue
        if set(line) <= {"-", " "}:
            continue
        columns = split_table_columns(line)
        if len(columns) >= 3 and columns[1] == package_id:
            return columns[2]
    return None


def parse_choco_version(package_name: str, result: dict) -> str | None:
    stdout = result.get("stdout")
    if not result.get("ok") or not stdout:
        return None
    for raw_line in str(stdout).splitlines():
        line = raw_line.strip()
        if not line or "|" not in line:
            continue
        name, candidate_version = line.split("|", 1)
        if name.lower() in {"id", "packageid"}:
            continue
        if name == package_name:
            return candidate_version.strip()
    return None


def parse_pacman_version(name: str, result: dict) -> str | None:
    del name
    line = result.get("stdout")
    if not result.get("ok") or not line:
        return None
    parts = str(line).split(maxsplit=1)
    return parts[1] if len(parts) == 2 else None


__all__ = [
    "parse_brew_version",
    "parse_choco_version",
    "parse_pacman_version",
    "parse_winget_version",
]
