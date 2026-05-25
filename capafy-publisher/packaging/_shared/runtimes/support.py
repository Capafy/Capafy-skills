from __future__ import annotations
from typing import Optional

import shutil
import subprocess


def unique_non_empty_strings(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    seen: set[str] = set()
    normalized: list[str] = []
    for item in values:
        text = str(item).strip()
        if not text or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    return normalized


def collect_optional_command_first_line(args: list[str], timeout: int = 10) -> Optional[str]:
    if not args or shutil.which(args[0]) is None:
        return None
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    output = (result.stdout or "").strip() or (result.stderr or "").strip()
    if not output:
        return None
    for line in output.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


__all__ = [
    "collect_optional_command_first_line",
    "unique_non_empty_strings",
]
