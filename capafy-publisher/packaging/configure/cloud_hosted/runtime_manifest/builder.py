from __future__ import annotations
from typing import Optional

import json
import logging
import platform
import shutil
from pathlib import Path

from packaging._shared.common.constants import (
    SYSTEM_COMPONENT_COMMANDS,
    SYSTEM_PACKAGE_CANDIDATES,
    VERSION_COMMANDS,
)
from .dependency_manifest import write_runtime_dependencies_manifest
from .system_commands import run_text_command
from .system_package_collectors import collect_command_version, collect_npm_global_packages
from .system_package_detection import detect_system_packages
from .system_summary import read_os_release, system_summary
from .ubuntu_packages import derive_ubuntu_system_packages


logger = logging.getLogger(__name__)


def write_runtime_environment_manifest(staging_root: Path, extra_payload: Optional[dict] = None) -> Path:
    tool_versions = []
    for name, args in {**VERSION_COMMANDS, **SYSTEM_COMPONENT_COMMANDS}.items():
        snapshot = collect_command_version(
            name,
            args,
            which=shutil.which,
            run_command=run_text_command,
        )
        if snapshot is not None:
            tool_versions.append(snapshot)
    tool_versions.sort(key=lambda item: str(item.get("name", "")))
    system_packages = detect_system_packages(
        candidates=SYSTEM_PACKAGE_CANDIDATES,
        which=shutil.which,
        run_command=run_text_command,
        system_name=platform.system(),
        log=logger,
    )
    payload = {
        "system": system_summary(
            read_release=read_os_release,
            platform_module=platform,
        ),
        "tools": tool_versions,
        "npm_global_packages": collect_npm_global_packages(
            which=shutil.which,
            run_command=run_text_command,
            log=logger,
        ),
        "system_packages": system_packages,
        "ubuntu_system_packages": derive_ubuntu_system_packages(system_packages),
    }
    if extra_payload:
        payload.update(extra_payload)
    output_path = staging_root / "agent.runtime_environment.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


__all__ = [
    "write_runtime_dependencies_manifest",
    "write_runtime_environment_manifest",
]
