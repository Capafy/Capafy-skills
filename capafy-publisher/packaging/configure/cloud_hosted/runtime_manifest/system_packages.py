from __future__ import annotations

import logging
import platform
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence

from packaging._shared.common.constants import SYSTEM_PACKAGE_CANDIDATES
from packaging.configure.cloud_hosted.runtime_manifest import system_package_collectors
from packaging.configure.cloud_hosted.runtime_manifest import system_package_detection
from packaging.configure.cloud_hosted.runtime_manifest import system_summary as system_summary_module
from packaging.configure.cloud_hosted.runtime_manifest.system_package_helpers import (
    TABLE_SPLIT_PATTERN,
    extract_named_versions,
    fallback_os_release_value,
    first_output_line,
    format_command,
    split_table_columns,
)


logger = logging.getLogger(__name__)


def _runtime_candidates(
    candidates: Mapping[str, Sequence[str]] | None,
) -> Mapping[str, Sequence[str]]:
    return SYSTEM_PACKAGE_CANDIDATES if candidates is None else candidates


def _runtime_which(
    which: Callable[[str], str | None] | None,
) -> Callable[[str], str | None]:
    return shutil.which if which is None else which


def _runtime_run_command(
    run_command: Callable[[list[str], int], dict] | None,
) -> Callable[[list[str], int], dict]:
    return run_text_command if run_command is None else run_command


def _runtime_logger(log: logging.Logger | None) -> logging.Logger:
    return logger if log is None else log


def run_text_command(args: list[str], timeout: int = 10) -> dict:

    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {
            "ok": False,
            "error": type(exc).__name__,
        }

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    payload = {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
    }
    if stdout:
        payload["stdout"] = stdout
    if stderr:
        payload["stderr"] = stderr
    return payload


def read_os_release() -> dict[str, str]:
    return system_summary_module.read_os_release()


def collect_command_version(
    name: str,
    args: list[str],
    *,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
) -> dict | None:
    return system_package_collectors.collect_command_version(
        name,
        args,
        which=_runtime_which(which),
        run_command=_runtime_run_command(run_command),
    )


def collect_per_candidate(
    executable: str,
    candidate_key: str,
    make_args: Callable[[str], list[str]],
    parse_version: Callable[[str, dict], str | None],
    timeout: int = 5,
    *,
    candidates: Mapping[str, Sequence[str]] | None = None,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
) -> list[dict[str, str]]:
    return system_package_collectors.collect_per_candidate(
        executable,
        candidate_key,
        make_args,
        parse_version,
        timeout,
        candidates=_runtime_candidates(candidates),
        which=_runtime_which(which),
        run_command=_runtime_run_command(run_command),
    )


def version_from_stdout(name: str, result: dict) -> str | None:
    return system_package_collectors.version_from_stdout(name, result)




def collect_npm_global_packages(
    *,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
    log: logging.Logger | None = None,
) -> list[dict[str, str]]:
    return system_package_collectors.collect_npm_global_packages(
        which=_runtime_which(which),
        run_command=_runtime_run_command(run_command),
        log=_runtime_logger(log),
    )


def collect_apt_packages(
    *,
    candidates: Mapping[str, Sequence[str]] | None = None,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
) -> list[dict[str, str]]:
    return system_package_collectors.collect_apt_packages(
        candidates=_runtime_candidates(candidates),
        which=_runtime_which(which),
        run_command=_runtime_run_command(run_command),
    )


def collect_brew_packages(
    *,
    candidates: Mapping[str, Sequence[str]] | None = None,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
) -> list[dict[str, str]]:
    return system_package_collectors.collect_brew_packages(
        candidates=_runtime_candidates(candidates),
        which=_runtime_which(which),
        run_command=_runtime_run_command(run_command),
    )


def collect_winget_packages(
    *,
    candidates: Mapping[str, Sequence[str]] | None = None,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
) -> list[dict[str, str]]:
    return system_package_collectors.collect_winget_packages(
        candidates=_runtime_candidates(candidates),
        which=_runtime_which(which),
        run_command=_runtime_run_command(run_command),
    )


def collect_choco_packages(
    *,
    candidates: Mapping[str, Sequence[str]] | None = None,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
) -> list[dict[str, str]]:
    return system_package_collectors.collect_choco_packages(
        candidates=_runtime_candidates(candidates),
        which=_runtime_which(which),
        run_command=_runtime_run_command(run_command),
    )


def collect_scoop_packages(
    *,
    candidates: Mapping[str, Sequence[str]] | None = None,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
    log: logging.Logger | None = None,
) -> list[dict[str, str]]:
    return system_package_collectors.collect_scoop_packages(
        candidates=_runtime_candidates(candidates),
        which=_runtime_which(which),
        run_command=_runtime_run_command(run_command),
        log=_runtime_logger(log),
    )


def collect_rpm_family_packages(
    candidate_key: str,
    *,
    candidates: Mapping[str, Sequence[str]] | None = None,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
) -> list[dict[str, str]]:
    return system_package_collectors.collect_rpm_family_packages(
        candidate_key,
        candidates=_runtime_candidates(candidates),
        which=_runtime_which(which),
        run_command=_runtime_run_command(run_command),
    )


def collect_apk_packages(
    *,
    candidates: Mapping[str, Sequence[str]] | None = None,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
) -> list[dict[str, str]]:
    return system_package_collectors.collect_apk_packages(
        candidates=_runtime_candidates(candidates),
        which=_runtime_which(which),
        run_command=_runtime_run_command(run_command),
    )


def collect_pacman_packages(
    *,
    candidates: Mapping[str, Sequence[str]] | None = None,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
) -> list[dict[str, str]]:
    return system_package_collectors.collect_pacman_packages(
        candidates=_runtime_candidates(candidates),
        which=_runtime_which(which),
        run_command=_runtime_run_command(run_command),
    )


def detect_windows_system_packages(
    *,
    candidates: Mapping[str, Sequence[str]] | None = None,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
    log: logging.Logger | None = None,
) -> dict:
    return system_package_detection.detect_windows_system_packages(
        candidates=_runtime_candidates(candidates),
        which=_runtime_which(which),
        run_command=_runtime_run_command(run_command),
        log=_runtime_logger(log),
    )


def detect_linux_system_packages(
    *,
    candidates: Mapping[str, Sequence[str]] | None = None,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
) -> dict:
    return system_package_detection.detect_linux_system_packages(
        candidates=_runtime_candidates(candidates),
        which=_runtime_which(which),
        run_command=_runtime_run_command(run_command),
    )


def detect_system_packages(
    *,
    candidates: Mapping[str, Sequence[str]] | None = None,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
    system_name: str | None = None,
    log: logging.Logger | None = None,
) -> dict:
    return system_package_detection.detect_system_packages(
        candidates=_runtime_candidates(candidates),
        which=_runtime_which(which),
        run_command=_runtime_run_command(run_command),
        system_name=system_name or platform.system(),
        log=_runtime_logger(log),
    )


def system_summary(
    *,
    read_release: Callable[[], dict[str, str]] = read_os_release,
    platform_module=platform,
) -> dict[str, str | None]:
    return system_summary_module.system_summary(
        read_release=read_release,
        platform_module=platform_module,
    )


__all__ = [
    "collect_apk_packages",
    "collect_apt_packages",
    "collect_brew_packages",
    "collect_choco_packages",
    "collect_command_version",
    "collect_npm_global_packages",
    "collect_pacman_packages",
    "collect_per_candidate",
    "collect_rpm_family_packages",
    "collect_scoop_packages",
    "collect_winget_packages",
    "detect_linux_system_packages",
    "detect_system_packages",
    "detect_windows_system_packages",
    "extract_named_versions",
    "first_output_line",
    "format_command",
    "read_os_release",
    "run_text_command",
    "split_table_columns",
    "system_summary",
    "version_from_stdout",
]
