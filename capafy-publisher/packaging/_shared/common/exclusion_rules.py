from __future__ import annotations
from collections.abc import Callable
from typing import Optional

from pathlib import PurePosixPath


SYSTEM_DIRS = {".git", ".github", "__pycache__", "node_modules", ".venv", "venv"}

SYSTEM_SUFFIXES = {".pyc", ".pyo"}

STAGE_EXCLUDED_DIRS = SYSTEM_DIRS | {
    "memory",
    ".temp",
    ".temp-fallback",
    ".ssh",
    ".gnupg",
    ".purple",
}

STAGE_EXCLUDED_SUFFIXES = {
    ".pyc", ".pyo", ".log",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".ppk",
    ".keychain",
    ".keychain-db",
    ".keystore",
    ".jks",
    ".kdb",
    ".kdbx",
    ".kwallet",
    ".agilekeychain",
    ".ovpn",
}

_NON_CREDENTIAL_EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log"}

CREDENTIAL_EXCLUDED_SUFFIXES = STAGE_EXCLUDED_SUFFIXES - _NON_CREDENTIAL_EXCLUDED_SUFFIXES

PRIVATE_KEY_FILE_BASENAMES = {
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
}
HIGH_RISK_FILE_BASENAMES = PRIVATE_KEY_FILE_BASENAMES | {
    ".credentials.json",
}
SPECIAL_SCAN_PATH_SUFFIXES = (
    ".aws/credentials",
    ".docker/config.json",
    ".gem/credentials",
    ".kube/config",
    ".m2/settings.xml",
)

EXCLUDE_FILE_SUFFIXES = (
    ".claude/.credentials.json",
    ".claude/.claude.json",
    ".codex/auth-profiles.json",
    ".codex/auth.json",
    ".openclaw/agents/main/agent/auth-profiles.json",
    ".openclaw/workspace/auth-profiles.json",
)

SOURCE_CODE_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".php",
    ".py",
    ".pyi",
    ".rb",
    ".rs",
    ".scala",
    ".swift",
    ".ts",
    ".tsx",
}


def make_skip_scan_predicate(*suffixes: str) -> Callable[[str], bool]:
    normalized_suffixes = tuple(
        str(suffix or "").replace("\\", "/").lower()
        for suffix in suffixes
        if str(suffix or "").strip()
    )

    def check(relpath: str) -> bool:
        normalized = str(relpath or "").replace("\\", "/").lower()
        return any(normalized.endswith(suffix) for suffix in normalized_suffixes)

    return check


def looks_like_high_risk_file(relpath: str) -> Optional[str]:
    pure = PurePosixPath(relpath)
    basename = pure.name
    lowered_basename = basename.lower()
    lowered = relpath.lower()

    if lowered_basename in HIGH_RISK_FILE_BASENAMES:
        return f"Filename matches {basename}"

    for suffix in EXCLUDE_FILE_SUFFIXES:
        if lowered.endswith(suffix):
            return f"Filename matches {suffix}"

    if lowered_basename.endswith((".key", ".p12", ".pfx")):
        return f"Filename matches {basename}"
    return None


__all__ = [
    "CREDENTIAL_EXCLUDED_SUFFIXES",
    "EXCLUDE_FILE_SUFFIXES",
    "HIGH_RISK_FILE_BASENAMES",
    "looks_like_high_risk_file",
    "make_skip_scan_predicate",
    "PRIVATE_KEY_FILE_BASENAMES",
    "SOURCE_CODE_SUFFIXES",
    "SPECIAL_SCAN_PATH_SUFFIXES",
    "STAGE_EXCLUDED_DIRS",
    "STAGE_EXCLUDED_SUFFIXES",
    "SYSTEM_DIRS",
    "SYSTEM_SUFFIXES",
]
