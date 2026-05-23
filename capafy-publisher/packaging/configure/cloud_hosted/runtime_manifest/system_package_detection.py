from __future__ import annotations

import logging
import platform
import shutil
from collections.abc import Callable, Mapping, Sequence

from packaging._shared.common.constants import SYSTEM_PACKAGE_CANDIDATES
from packaging.configure.cloud_hosted.runtime_manifest.system_package_collectors import (
    collect_apt_packages,
    collect_apk_packages,
    collect_brew_packages,
    collect_choco_packages,
    collect_pacman_packages,
    collect_rpm_family_packages,
    collect_scoop_packages,
    collect_winget_packages,
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


def _runtime_logger(log: logging.Logger | None) -> logging.Logger:
    return logger if log is None else log


def detect_windows_system_packages(
    *,
    candidates: Mapping[str, Sequence[str]] | None = None,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
    log: logging.Logger | None = None,
) -> dict:
    candidates = _runtime_candidates(candidates)
    which = _runtime_which(which)
    log = _runtime_logger(log)
    if which("winget") is not None:
        return {"manager": "winget", "packages": collect_winget_packages(candidates=candidates, which=which, run_command=run_command)}
    if which("choco") is not None:
        return {"manager": "choco", "packages": collect_choco_packages(candidates=candidates, which=which, run_command=run_command)}
    if which("scoop") is not None:
        return {"manager": "scoop", "packages": collect_scoop_packages(candidates=candidates, which=which, run_command=run_command, log=log)}
    return {"manager": None, "packages": []}


def detect_linux_system_packages(
    *,
    candidates: Mapping[str, Sequence[str]] | None = None,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
) -> dict:
    candidates = _runtime_candidates(candidates)
    which = _runtime_which(which)
    if which("dpkg-query") is not None:
        return {"manager": "apt", "packages": collect_apt_packages(candidates=candidates, which=which, run_command=run_command)}
    if which("dnf") is not None:
        return {"manager": "dnf", "packages": collect_rpm_family_packages("dnf", candidates=candidates, which=which, run_command=run_command)}
    if which("yum") is not None:
        return {"manager": "yum", "packages": collect_rpm_family_packages("yum", candidates=candidates, which=which, run_command=run_command)}
    if which("rpm") is not None:
        return {"manager": "rpm", "packages": collect_rpm_family_packages("rpm", candidates=candidates, which=which, run_command=run_command)}
    if which("apk") is not None:
        return {"manager": "apk", "packages": collect_apk_packages(candidates=candidates, which=which, run_command=run_command)}
    if which("pacman") is not None:
        return {"manager": "pacman", "packages": collect_pacman_packages(candidates=candidates, which=which, run_command=run_command)}
    if which("brew") is not None:
        return {"manager": "brew", "packages": collect_brew_packages(candidates=candidates, which=which, run_command=run_command)}
    return {"manager": None, "packages": []}


def detect_system_packages(
    *,
    candidates: Mapping[str, Sequence[str]] | None = None,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
    system_name: str | None = None,
    log: logging.Logger | None = None,
) -> dict:
    candidates = _runtime_candidates(candidates)
    which = _runtime_which(which)
    log = _runtime_logger(log)
    system = system_name or platform.system()
    if system == "Windows":
        return detect_windows_system_packages(candidates=candidates, which=which, run_command=run_command, log=log)
    if system == "Darwin":
        if which("brew") is not None:
            return {"manager": "brew", "packages": collect_brew_packages(candidates=candidates, which=which, run_command=run_command)}
        return {"manager": None, "packages": []}
    if system == "Linux":
        return detect_linux_system_packages(candidates=candidates, which=which, run_command=run_command)
    return {"manager": None, "packages": []}


__all__ = [
    "detect_linux_system_packages",
    "detect_system_packages",
    "detect_windows_system_packages",
]
