from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping, Sequence

from packaging.configure.cloud_hosted.runtime_manifest.system_package_helpers import (
    extract_named_versions,
    first_output_line,
)
from packaging.configure.cloud_hosted.runtime_manifest.system_package_parsers import (
    parse_brew_version,
    parse_choco_version,
    parse_pacman_version,
    parse_winget_version,
)
from packaging.configure.cloud_hosted.runtime_manifest.system_package_probe import (
    collect_command_version,
    collect_per_candidate,
    runtime_candidates,
    runtime_logger,
    runtime_run_command,
    runtime_which,
    version_from_stdout,
)


logger = logging.getLogger(__name__)


def collect_npm_global_packages(
    *,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
    log: logging.Logger | None = None,
) -> list[dict[str, str]]:
    which = runtime_which(which)
    run_command = runtime_run_command(run_command)
    log = runtime_logger(logger, log)
    if which("npm") is None:
        return []
    list_result = run_command(["npm", "list", "-g", "--depth=0", "--json"], 20)
    if not list_result.get("ok"):
        return []

    try:
        parsed = json.loads(list_result.get("stdout", "{}"))
    except json.JSONDecodeError as exc:
        log.warning("failed to parse npm global package JSON: %s", exc)
        return []

    dependencies = parsed.get("dependencies", {})
    if isinstance(dependencies, dict):
        return [
            {"name": name, "version": str(info.get("version", ""))}
            for name, info in sorted(dependencies.items())
            if isinstance(info, dict)
        ]
    return []


def collect_apt_packages(
    *,
    candidates: Mapping[str, Sequence[str]] | None = None,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
) -> list[dict[str, str]]:
    return collect_per_candidate(
        "dpkg-query", "apt",
        make_args=lambda pkg: ["dpkg-query", "-W", "-f=${Version}", pkg],
        parse_version=version_from_stdout,
        candidates=candidates,
        which=which,
        run_command=run_command,
    )


def collect_brew_packages(
    *,
    candidates: Mapping[str, Sequence[str]] | None = None,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
) -> list[dict[str, str]]:
    return collect_per_candidate(
        "brew", "brew",
        make_args=lambda pkg: ["brew", "list", "--versions", pkg],
        parse_version=parse_brew_version,
        timeout=10,
        candidates=candidates,
        which=which,
        run_command=run_command,
    )


def collect_winget_packages(
    *,
    candidates: Mapping[str, Sequence[str]] | None = None,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
) -> list[dict[str, str]]:
    return collect_per_candidate(
        "winget", "winget",
        make_args=lambda pkg: [
            "winget", "list", "--id", pkg, "--exact",
            "--accept-source-agreements", "--disable-interactivity",
        ],
        parse_version=parse_winget_version,
        timeout=20,
        candidates=candidates,
        which=which,
        run_command=run_command,
    )


def collect_choco_packages(
    *,
    candidates: Mapping[str, Sequence[str]] | None = None,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
) -> list[dict[str, str]]:
    return collect_per_candidate(
        "choco", "choco",
        make_args=lambda pkg: ["choco", "list", "--local-only", "--limit-output", pkg],
        parse_version=parse_choco_version,
        timeout=15,
        candidates=candidates,
        which=which,
        run_command=run_command,
    )


def collect_scoop_packages(
    *,
    candidates: Mapping[str, Sequence[str]] | None = None,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
    log: logging.Logger | None = None,
) -> list[dict[str, str]]:
    candidates = runtime_candidates(candidates)
    which = runtime_which(which)
    run_command = runtime_run_command(run_command)
    log = runtime_logger(logger, log)
    if which("scoop") is None:
        return []

    result = run_command(["scoop", "export"], 20)
    stdout = result.get("stdout")
    if not result.get("ok") or not stdout:
        return []

    try:
        parsed = json.loads(str(stdout))
    except json.JSONDecodeError as exc:
        log.warning("failed to parse scoop export JSON: %s", exc)
        return []

    exported_versions = extract_named_versions(parsed)
    packages: list[dict[str, str]] = []
    for package_name in candidates["scoop"]:
        version = exported_versions.get(package_name)
        if version:
            packages.append({"name": package_name, "version": version})
    return packages


def collect_rpm_family_packages(
    candidate_key: str,
    *,
    candidates: Mapping[str, Sequence[str]] | None = None,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
) -> list[dict[str, str]]:
    return collect_per_candidate(
        "rpm", candidate_key,
        make_args=lambda pkg: ["rpm", "-q", "--qf", "%{VERSION}-%{RELEASE}", pkg],
        parse_version=version_from_stdout,
        candidates=candidates,
        which=which,
        run_command=run_command,
    )


def collect_apk_packages(
    *,
    candidates: Mapping[str, Sequence[str]] | None = None,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
) -> list[dict[str, str]]:
    run_command = runtime_run_command(run_command)

    def _parse(package_name: str, result: dict) -> str | None:
        if not result.get("ok"):
            return None
        version_result = run_command(["apk", "info", "-v", package_name], 5)
        line = first_output_line(version_result)
        if not line:
            return None
        version = str(line)
        prefix = f"{package_name}-"
        if version.startswith(prefix):
            version = version[len(prefix):]
        return version

    return collect_per_candidate(
        "apk", "apk",
        make_args=lambda pkg: ["apk", "info", "-e", pkg],
        parse_version=_parse,
        candidates=candidates,
        which=which,
        run_command=run_command,
    )


def collect_pacman_packages(
    *,
    candidates: Mapping[str, Sequence[str]] | None = None,
    which: Callable[[str], str | None] | None = None,
    run_command: Callable[[list[str], int], dict] | None = None,
) -> list[dict[str, str]]:
    return collect_per_candidate(
        "pacman", "pacman",
        make_args=lambda pkg: ["pacman", "-Q", pkg],
        parse_version=parse_pacman_version,
        candidates=candidates,
        which=which,
        run_command=run_command,
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
    "version_from_stdout",
]
