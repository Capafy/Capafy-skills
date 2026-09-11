from __future__ import annotations
from typing import Optional

from pathlib import PurePosixPath

from packaging.common.constants import DEPENDENCY_MANIFEST_FILES


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

CONTENT_SCAN_EXCLUDED_FILES = frozenset(DEPENDENCY_MANIFEST_FILES)

TEXT_FILE_SUFFIXES = frozenset({
    ".cfg",
    ".conf",
    ".env",
    ".ini",
    ".json",
    ".json5",
    ".jsonc",
    ".md",
    ".markdown",
    ".mdx",
    ".rst",
    ".toml",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
})

TEXT_FILE_BASENAMES = frozenset({
    "AGENTS.md",
    "CHANGELOG.md",
    "CLAUDE.md",
    "LICENSE",
    "LICENSE.md",
    "README",
    "README.md",
    "SKILL.md",
    "TODO.md",
})


def should_skip_content_scan_for_file(path: str) -> bool:
    basename = PurePosixPath(str(path or "").replace("\\", "/")).name
    return basename in CONTENT_SCAN_EXCLUDED_FILES


def is_content_scan_text_file(path: object) -> bool:
    pure = PurePosixPath(str(path or "").replace("\\", "/"))
    if pure.name in CONTENT_SCAN_EXCLUDED_FILES:
        return False
    return (
        pure.name in TEXT_FILE_BASENAMES
        or pure.name.startswith(".env")
        or pure.suffix.lower() in TEXT_FILE_SUFFIXES
    )


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
    "CONTENT_SCAN_EXCLUDED_FILES",
    "CREDENTIAL_EXCLUDED_SUFFIXES",
    "EXCLUDE_FILE_SUFFIXES",
    "HIGH_RISK_FILE_BASENAMES",
    "is_content_scan_text_file",
    "looks_like_high_risk_file",
    "PRIVATE_KEY_FILE_BASENAMES",
    "SOURCE_CODE_SUFFIXES",
    "SPECIAL_SCAN_PATH_SUFFIXES",
    "STAGE_EXCLUDED_DIRS",
    "STAGE_EXCLUDED_SUFFIXES",
    "SYSTEM_DIRS",
    "SYSTEM_SUFFIXES",
    "TEXT_FILE_BASENAMES",
    "TEXT_FILE_SUFFIXES",
    "should_skip_content_scan_for_file",
]
