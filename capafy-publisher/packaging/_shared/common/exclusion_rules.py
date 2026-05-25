from __future__ import annotations
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

_NO_AUTH_NEUTRAL_EXCLUDED_DIRS = SYSTEM_DIRS | {
    "memory",
    ".temp",
    ".temp-fallback",
}

CREDENTIAL_EXCLUDED_DIRS = STAGE_EXCLUDED_DIRS - _NO_AUTH_NEUTRAL_EXCLUDED_DIRS

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

_SCAN_EXCLUDED_FILE_EXTENSION_CANDIDATES = {
    ".jks",
    ".key",
    ".keystore",
    ".p12",
    ".pem",
    ".pfx",
}
_SCAN_EXCLUDED_FILE_EXTENSIONS = tuple(
    sorted(STAGE_EXCLUDED_SUFFIXES & _SCAN_EXCLUDED_FILE_EXTENSION_CANDIDATES)
)

_COMMON_CREDENTIAL_FILE_BASENAMES: set[str] = set()

STAGE_EXCLUDED_FILES = _COMMON_CREDENTIAL_FILE_BASENAMES

PRIVATE_KEY_FILE_BASENAMES = {
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
}
_SCAN_EXCLUDED_FILE_BASENAMES = _COMMON_CREDENTIAL_FILE_BASENAMES | PRIVATE_KEY_FILE_BASENAMES

STAGE_EXCLUDED_NAME_PATTERNS: tuple = ()

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


def looks_like_high_risk_file(relpath: str) -> Optional[str]:
    pure = PurePosixPath(relpath)
    basename = pure.name
    lowered_basename = basename.lower()
    lowered = relpath.lower()

    if lowered_basename in PRIVATE_KEY_FILE_BASENAMES:
        return f"Filename matches {basename}"

    for suffix in EXCLUDE_FILE_SUFFIXES:
        if lowered.endswith(suffix):
            return f"Filename matches {suffix}"

    if lowered_basename.endswith((".key", ".p12", ".pfx")):
        return f"Filename matches {basename}"
    return None


def exclude_reason_code_for_path(relpath: str, *, reason: str = "") -> Optional[str]:
    normalized = str(relpath or "").strip().rstrip("/")
    if not normalized:
        return None
    pure = PurePosixPath(normalized)
    basename = pure.name.lower()
    lowered = normalized.lower()
    lowered_reason = str(reason or "").strip().lower()

    if "private key" in lowered_reason:
        return "private_key"

    if basename.endswith(_SCAN_EXCLUDED_FILE_EXTENSIONS):
        if basename.endswith(".key"):
            return "private_key"
        return "cert"

    if basename in _SCAN_EXCLUDED_FILE_BASENAMES:
        return "known_credential_file"
    if any(lowered.endswith(suffix) for suffix in EXCLUDE_FILE_SUFFIXES):
        return "known_credential_file"
    if looks_like_high_risk_file(normalized):
        return "known_credential_file"
    return None


def default_exclude_use(relpath: str, *, reason_code: str) -> str:
    if reason_code == "private_key":
        return "Private key file excluded from package"
    if reason_code == "cert":
        return "Certificate or keystore file excluded from package"
    if any(str(relpath or "").strip().lower().endswith(suffix) for suffix in EXCLUDE_FILE_SUFFIXES):
        return "Login credential file excluded from package"
    return "Credential file excluded from package"


__all__ = [
    "CREDENTIAL_EXCLUDED_DIRS",
    "CREDENTIAL_EXCLUDED_SUFFIXES",
    "default_exclude_use",
    "exclude_reason_code_for_path",
    "EXCLUDE_FILE_SUFFIXES",
    "looks_like_high_risk_file",
    "PRIVATE_KEY_FILE_BASENAMES",
    "SOURCE_CODE_SUFFIXES",
    "SPECIAL_SCAN_PATH_SUFFIXES",
    "STAGE_EXCLUDED_DIRS",
    "STAGE_EXCLUDED_FILES",
    "STAGE_EXCLUDED_NAME_PATTERNS",
    "STAGE_EXCLUDED_SUFFIXES",
    "SYSTEM_DIRS",
    "SYSTEM_SUFFIXES",
]
