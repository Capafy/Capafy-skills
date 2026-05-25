from __future__ import annotations
from typing import Optional

import logging
import re
import shutil
from collections.abc import Callable, Mapping, Sequence

from packaging._shared.common.constants import SYSTEM_PACKAGE_CANDIDATES
from packaging.configure.cloud_hosted.runtime_manifest.system_commands import run_text_command as _default_run_text_command
from packaging.configure.cloud_hosted.runtime_manifest.system_package_helpers import (
    first_output_line,
    format_command,
)


_PIP_VERSION_FROM_PATH_PATTERN = re.compile(
    r"(?i)^(?P<prefix>pip\s+\S+)\s+from\s+.+?\s+(?P<python>\(python\s+[^)]+\))$"
)


def normalize_command_version(name: str, version: str) -> str:
    if name == "pip":
        match = _PIP_VERSION_FROM_PATH_PATTERN.match(version.strip())
        if match:
            return f"{match.group('prefix')} {match.group('python')}"
    return version


def runtime_candidates(
    candidates: Optional[Mapping[str, Sequence[str]]],
) -> Mapping[str, Sequence[str]]:
    return SYSTEM_PACKAGE_CANDIDATES if candidates is None else candidates


def runtime_which(
    which: Optional[Callable[[str], Optional[str]]],
) -> Callable[[str], Optional[str]]:
    return shutil.which if which is None else which


def runtime_logger(default_logger: logging.Logger, log: Optional[logging.Logger]) -> logging.Logger:
    return default_logger if log is None else log


def runtime_run_command(
    run_command: Optional[Callable[[list[str], int], dict]],
) -> Callable[[list[str], int], dict]:
    return _default_run_text_command if run_command is None else run_command


def collect_command_version(
    name: str,
    args: list[str],
    *,
    which: Optional[Callable[[str], Optional[str]]] = None,
    run_command: Optional[Callable[[list[str], int], dict]] = None,
) -> Optional[dict]:
    resolved_which = runtime_which(which)
    resolved_run_command = runtime_run_command(run_command)
    executable = args[0]
    path = resolved_which(executable)
    if path is None:
        return None
    result = resolved_run_command(args, 10)
    version = first_output_line(result)
    if not version:
        return None
    version = normalize_command_version(name, version)
    return {
        "name": name,
        "version": version,
        "command": format_command(args),
    }


def collect_per_candidate(
    executable: str,
    candidate_key: str,
    make_args: Callable[[str], list[str]],
    parse_version: Callable[[str, dict], Optional[str]],
    timeout: int = 5,
    *,
    candidates: Optional[Mapping[str, Sequence[str]]] = None,
    which: Optional[Callable[[str], Optional[str]]] = None,
    run_command: Optional[Callable[[list[str], int], dict]] = None,
) -> list[dict[str, str]]:
    resolved_candidates = runtime_candidates(candidates)
    resolved_which = runtime_which(which)
    resolved_run_command = runtime_run_command(run_command)
    if resolved_which(executable) is None:
        return []
    packages: list[dict[str, str]] = []
    for name in resolved_candidates[candidate_key]:
        result = resolved_run_command(make_args(name), timeout)
        version = parse_version(name, result)
        if version:
            packages.append({"name": name, "version": version})
    return packages


def version_from_stdout(name: str, result: dict) -> Optional[str]:
    del name
    if result.get("ok") and result.get("stdout"):
        return result["stdout"]
    return None


__all__ = [
    "collect_command_version",
    "collect_per_candidate",
    "normalize_command_version",
    "runtime_candidates",
    "runtime_logger",
    "runtime_run_command",
    "runtime_which",
    "version_from_stdout",
]
