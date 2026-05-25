from __future__ import annotations
from typing import Optional

import platform
import shlex
from collections.abc import Callable
from pathlib import Path

from packaging.configure.cloud_hosted.runtime_manifest.system_package_helpers import (
    fallback_os_release_value,
)


def read_os_release(os_release_path: Optional[Path] = None) -> dict[str, str]:
    path = os_release_path or Path("/etc/os-release")
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, raw_value = line.split("=", 1)
        normalized_raw_value = raw_value.strip()
        try:
            parsed_values = shlex.split(normalized_raw_value, posix=True)
        except ValueError:
            parsed_values = []
        if parsed_values:
            values[key] = parsed_values[0]
        else:
            values[key] = fallback_os_release_value(normalized_raw_value)
    return values


def system_summary(
    *,
    read_release: Callable[[], dict[str, str]] = read_os_release,
    platform_module=platform,
) -> dict[str, Optional[str]]:
    os_release = read_release()
    system_name = platform_module.system()
    display_os = (
        os_release.get("PRETTY_NAME")
        or os_release.get("NAME")
        or platform_module.platform()
    )
    return {
        "family": system_name,
        "os": display_os,
        "architecture": platform_module.machine(),
        "kernel": f"{system_name} {platform_module.release()}",
    }


__all__ = ["read_os_release", "system_summary"]
