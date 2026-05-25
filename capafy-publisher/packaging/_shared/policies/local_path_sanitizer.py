from __future__ import annotations
from typing import Optional

import re
from pathlib import Path

from packaging._shared.common.local_path_detection import (
    LOCAL_PATH_PLACEHOLDER,
    redact_local_traces_in_text,
)


_WINDOWS_USER_PATH_PATTERN = re.compile(
    r"(?i)\b[A-Z]:(?P<sep>[\\/]+)(?:Users|Documents and Settings)[\\/]+[^\\/\r\n\s'\"<>:,;]+(?P<tail>[\\/]+[^\r\n'\"<>:,;]*)?"
)
_POSIX_USER_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9._~-])/(?:(?:home|Users)/[^/\r\n\s'\"<>:,;]+)(?P<tail>(?:/[^\r\n\s'\"<>:,;]+)*)"
)
_WINDOWS_OPENCLAW_HOME_PATH_PATTERN = re.compile(
    r"(?i)\b[A-Z]:[\\/]+(?:Users|Documents and Settings)[\\/]+[^\\/\r\n\s'\"<>:,;]+[\\/]+\.openclaw(?:[\\/]+[^\r\n'\"<>:,;]*)?"
)
_POSIX_OPENCLAW_HOME_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9._~-])/(?:(?:home|Users)/[^/\r\n\s'\"<>:,;]+)/\.openclaw(?:/[^\r\n\s'\"<>:,;]+)*"
)
def replace_known_path_refs(text: str, refs: dict[str, str]) -> tuple[str, int]:
    updated = text
    replacements = 0
    for source_path, packaged_path in sorted(refs.items(), key=lambda item: len(item[0]), reverse=True):
        normalized_source = str(source_path or "").strip()
        normalized_packaged = str(packaged_path or "").strip()
        if not normalized_source or not normalized_packaged:
            continue
        count = updated.count(normalized_source)
        if not count:
            continue
        updated = updated.replace(normalized_source, normalized_packaged)
        replacements += count
    return updated, replacements


def redact_openclaw_home_path_refs(text: str) -> tuple[str, int]:
    updated, windows_replacements = _WINDOWS_OPENCLAW_HOME_PATH_PATTERN.subn(LOCAL_PATH_PLACEHOLDER, text)
    updated, posix_replacements = _POSIX_OPENCLAW_HOME_PATH_PATTERN.subn(LOCAL_PATH_PLACEHOLDER, updated)
    return updated, windows_replacements + posix_replacements


def normalize_home_path_refs(text: str) -> tuple[str, int]:
    replacements = 0

    def replace_windows_user_path(match: re.Match[str]) -> str:
        nonlocal replacements
        replacements += 1
        sep = "\\" if "\\" in (match.group("sep") or "") else "/"
        normalized_tail = re.sub(r"[\\/]+", lambda _match: sep, match.group("tail") or "")
        return "~" + normalized_tail

    def replace_posix_user_path(match: re.Match[str]) -> str:
        nonlocal replacements
        replacements += 1
        return "~" + (match.group("tail") or "")

    updated = _WINDOWS_USER_PATH_PATTERN.sub(replace_windows_user_path, text)
    updated = _POSIX_USER_PATH_PATTERN.sub(replace_posix_user_path, updated)
    return updated, replacements


def rewrite_local_path_text(
    value: str,
    *,
    packaged_path_refs: dict[str, str],
    source_path: Optional[Path] = None,
) -> tuple[str, int]:
    updated, known_ref_replacements = replace_known_path_refs(value, packaged_path_refs)
    updated, openclaw_private_replacements = redact_openclaw_home_path_refs(updated)
    updated, home_replacements = normalize_home_path_refs(updated)
    updated, local_replacements = redact_local_traces_in_text(
        updated,
        replacement=LOCAL_PATH_PLACEHOLDER,
        source_path=source_path,
    )
    return (
        updated,
        known_ref_replacements
        + openclaw_private_replacements
        + home_replacements
        + local_replacements,
    )


__all__ = [
    "normalize_home_path_refs",
    "redact_openclaw_home_path_refs",
    "replace_known_path_refs",
    "rewrite_local_path_text",
]
