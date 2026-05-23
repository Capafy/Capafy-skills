from __future__ import annotations

import re
from pathlib import Path

from packaging._shared.policies.path_refs import is_packaged_runtime_ref


LOCAL_PATH_PLACEHOLDER = "LOCAL_PATH_REDACTED"

LOCAL_HOST_PATTERN = re.compile(
    r"(?i)(?:https?://)?(?:localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|"
    r"192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)(?::\d+)?(?:/[^\s'\"<>]*)?"
)

LOCAL_PATH_PATTERN = re.compile(
    r"(?i)(?:^|[\\/])(?:home|users)(?:[\\/]|$)|"
    r"^[A-Z]:[\\/]|^\\\\[^\\/\r\n]+\\|^\./|^\.\./"
)

_PUBLIC_PATH_PREFIXES = (
    "/usr/", "/etc/", "/bin/", "/sbin/",
    "/lib/", "/lib64/", "/lib32/",
    "/proc/", "/sys/", "/dev/", "/run/",
    "/tmp/", "/var/", "/opt/", "/srv/", "/mnt/",
    "/Library/Frameworks/", "/System/Library/", "/Applications/",
)
_MOUNTED_USER_HOME_PATH_PATTERN = re.compile(
    r"(?i)^/mnt/[a-z]/(?:Users|home)/[^/\s'\"<>:,;`)\]\}]+(?:/|$)"
)

_WINDOWS_PUBLIC_PATH_PATTERN = re.compile(
    r"(?i)^[A-Z]:[\\/]+(?:Windows|Program Files(?: \(x86\))?)[\\/]+"
)

_REMOTE_URL_PATTERN = re.compile(
    r"(?i)\b(?:https?|ftp|wss?)://[^\s'\"<>]+"
)

_PATH_TOKEN_PATTERN = re.compile(
    r"(?i)("
    r"(?<![A-Za-z0-9._~<>\-`])/[^\s'\"<>:,;`\)\]\}]+"
    r"|\.{1,2}/[^\s'\"<>:,;`\)\]\}]+"
    r"|~[\\/][^\s'\"<>:,;`\)\]\}]+"
    r"|(?<![A-Za-z0-9])[A-Z]:[\\/]+(?:[^\r\n'\"<>:,;`\|\s]|\s(?![A-Z]:[\\/]+|\|))+"
    r"|\\\\[^\\/\r\n\s]+\\[^\s'\"<>:,;`\)\]\}]+"
    r")"
)

_CODE_SYNTAX_TOKEN_PATTERN = re.compile(r"(?i)^//|^/[^\w./~-]")


def _iter_path_tokens(value: str) -> list[str]:
    return [match.group(0).strip().strip("'\"") for match in _PATH_TOKEN_PATTERN.finditer(value)]


_CODE_SYNTAX_FILE_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".cs",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".jsonc",
    ".json5",
    ".kt",
    ".rs",
    ".swift",
    ".ts",
    ".tsx",
}


def _should_skip_code_syntax_tokens(source_path: str | Path | None) -> bool:
    if source_path is None:
        return False
    suffix = Path(source_path).suffix.lower()
    return suffix in _CODE_SYNTAX_FILE_SUFFIXES


def _looks_like_code_syntax_token(token: str) -> bool:
    return bool(_CODE_SYNTAX_TOKEN_PATTERN.search(token.strip()))


def _is_public_system_path_token(token: str) -> bool:
    stripped = token.strip()
    if _MOUNTED_USER_HOME_PATH_PATTERN.match(stripped):
        return False
    if any(stripped.startswith(p) or stripped == p.rstrip("/\\") for p in _PUBLIC_PATH_PREFIXES):
        return True
    return bool(_WINDOWS_PUBLIC_PATH_PATTERN.match(stripped))


def looks_like_local_path(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    if LOCAL_HOST_PATTERN.search(stripped):
        return True
    cleaned = _REMOTE_URL_PATTERN.sub(" ", stripped)
    if not cleaned.strip():
        return False
    path_tokens = _iter_path_tokens(cleaned)
    if not path_tokens:
        return False
    for token in path_tokens:
        if is_packaged_runtime_ref(token):
            continue
        if token.startswith("~"):
            return True
        if bool(LOCAL_PATH_PATTERN.search(token)) and not _is_public_system_path_token(token):
            return True
    return False


def redact_local_traces_in_text(
    text: str,
    *,
    replacement: str = "[removed]",
    source_path: str | Path | None = None,
) -> tuple[str, int]:
    updated = text
    replacements = 0
    skip_code_syntax_tokens = _should_skip_code_syntax_tokens(source_path)

    def _replace_one(_match: object) -> str:
        nonlocal replacements
        replacements += 1
        return replacement

    updated = LOCAL_HOST_PATTERN.sub(_replace_one, updated)

    url_ranges = [(m.start(), m.end()) for m in _REMOTE_URL_PATTERN.finditer(updated)]

    def _in_url_range(start: int, end: int) -> bool:
        return any(rs <= start and end <= re_end for rs, re_end in url_ranges)

    def _maybe_replace_path_token(match) -> str:
        nonlocal replacements
        if _in_url_range(match.start(), match.end()):
            return match.group(0)
        token = match.group(0)
        if is_packaged_runtime_ref(token):
            return token
        if token.startswith("~"):
            replacements += 1
            return replacement
        if skip_code_syntax_tokens and _looks_like_code_syntax_token(token):
            return token
        if not LOCAL_PATH_PATTERN.search(token):
            return token
        if _is_public_system_path_token(token):
            return token
        replacements += 1
        return replacement

    updated = _PATH_TOKEN_PATTERN.sub(_maybe_replace_path_token, updated)

    return updated, replacements


__all__ = [
    "LOCAL_HOST_PATTERN",
    "LOCAL_PATH_PATTERN",
    "LOCAL_PATH_PLACEHOLDER",
    "looks_like_local_path",
    "redact_local_traces_in_text",
]
