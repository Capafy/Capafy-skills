from __future__ import annotations

import json
import logging
import platform
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from packaging._shared.common.constants import (
    SYSTEM_COMPONENT_COMMANDS,
    SYSTEM_PACKAGE_CANDIDATES,
    VERSION_COMMANDS,
)
from . import system_packages as _system_packages
from .dependency_manifest import write_runtime_dependencies_manifest
from .ubuntu_packages import derive_ubuntu_system_packages


logger = logging.getLogger(__name__)






TABLE_SPLIT_PATTERN = _system_packages.TABLE_SPLIT_PATTERN


def _run_text_command(args: list[str], timeout: int = 10) -> dict:
    return _system_packages.run_text_command(args, timeout=timeout)


def _first_output_line(payload: dict) -> str | None:
    return _system_packages.first_output_line(payload)


def _fallback_os_release_value(raw_value: str) -> str:
    return _system_packages.fallback_os_release_value(raw_value)


def _read_os_release() -> dict[str, str]:
    return _system_packages.read_os_release()


def _format_command(args: list[str]) -> str:
    return _system_packages.format_command(args)


def _split_table_columns(line: str) -> list[str]:
    return _system_packages.split_table_columns(line)


def _extract_named_versions(payload: object, versions: dict[str, str] | None = None) -> dict[str, str]:
    return _system_packages.extract_named_versions(payload, versions)


def _collect_command_version(name: str, args: list[str]) -> dict | None:
    return _system_packages.collect_command_version(
        name,
        args,
        which=shutil.which,
        run_command=_run_text_command,
    )


def _collect_per_candidate(
    executable: str,
    candidate_key: str,
    make_args: Callable[[str], list[str]],
    parse_version: Callable[[str, dict], str | None],
    timeout: int = 5,
) -> list[dict[str, str]]:
    return _system_packages.collect_per_candidate(
        executable,
        candidate_key,
        make_args,
        parse_version,
        timeout=timeout,
        candidates=SYSTEM_PACKAGE_CANDIDATES,
        which=shutil.which,
        run_command=_run_text_command,
    )


def _version_from_stdout(name: str, result: dict) -> str | None:
    return _system_packages.version_from_stdout(name, result)




def _collect_npm_global_packages() -> list[dict[str, str]]:
    return _system_packages.collect_npm_global_packages(
        which=shutil.which,
        run_command=_run_text_command,
        log=logger,
    )


def _collect_apt_packages() -> list[dict[str, str]]:
    return _system_packages.collect_apt_packages(
        candidates=SYSTEM_PACKAGE_CANDIDATES,
        which=shutil.which,
        run_command=_run_text_command,
    )


def _collect_brew_packages() -> list[dict[str, str]]:
    return _system_packages.collect_brew_packages(
        candidates=SYSTEM_PACKAGE_CANDIDATES,
        which=shutil.which,
        run_command=_run_text_command,
    )


def _collect_winget_packages() -> list[dict[str, str]]:
    return _system_packages.collect_winget_packages(
        candidates=SYSTEM_PACKAGE_CANDIDATES,
        which=shutil.which,
        run_command=_run_text_command,
    )


def _collect_choco_packages() -> list[dict[str, str]]:
    return _system_packages.collect_choco_packages(
        candidates=SYSTEM_PACKAGE_CANDIDATES,
        which=shutil.which,
        run_command=_run_text_command,
    )


def _collect_scoop_packages() -> list[dict[str, str]]:
    return _system_packages.collect_scoop_packages(
        candidates=SYSTEM_PACKAGE_CANDIDATES,
        which=shutil.which,
        run_command=_run_text_command,
        log=logger,
    )


def _collect_rpm_family_packages(candidate_key: str) -> list[dict[str, str]]:
    return _system_packages.collect_rpm_family_packages(
        candidate_key,
        candidates=SYSTEM_PACKAGE_CANDIDATES,
        which=shutil.which,
        run_command=_run_text_command,
    )


def _collect_apk_packages() -> list[dict[str, str]]:
    return _system_packages.collect_apk_packages(
        candidates=SYSTEM_PACKAGE_CANDIDATES,
        which=shutil.which,
        run_command=_run_text_command,
    )


def _collect_pacman_packages() -> list[dict[str, str]]:
    return _system_packages.collect_pacman_packages(
        candidates=SYSTEM_PACKAGE_CANDIDATES,
        which=shutil.which,
        run_command=_run_text_command,
    )







def _detect_windows_system_packages() -> dict:
    return _system_packages.detect_windows_system_packages(
        candidates=SYSTEM_PACKAGE_CANDIDATES,
        which=shutil.which,
        run_command=_run_text_command,
        log=logger,
    )


def _detect_linux_system_packages() -> dict:
    return _system_packages.detect_linux_system_packages(
        candidates=SYSTEM_PACKAGE_CANDIDATES,
        which=shutil.which,
        run_command=_run_text_command,
    )


def _detect_system_packages() -> dict:
    return _system_packages.detect_system_packages(
        candidates=SYSTEM_PACKAGE_CANDIDATES,
        which=shutil.which,
        run_command=_run_text_command,
        system_name=platform.system(),
        log=logger,
    )


def _system_summary() -> dict[str, str | None]:
    return _system_packages.system_summary(
        read_release=_read_os_release,
        platform_module=platform,
    )


def write_runtime_environment_manifest(staging_root: Path, extra_payload: dict | None = None) -> Path:
    tool_versions = []
    for name, args in {**VERSION_COMMANDS, **SYSTEM_COMPONENT_COMMANDS}.items():
        snapshot = _collect_command_version(name, args)
        if snapshot is not None:
            tool_versions.append(snapshot)
    tool_versions.sort(key=lambda item: str(item.get("name", "")))
    system_packages = _detect_system_packages()
    payload = {
        "system": _system_summary(),
        "tools": tool_versions,
        "npm_global_packages": _collect_npm_global_packages(),
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
