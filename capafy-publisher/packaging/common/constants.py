from __future__ import annotations

from pathlib import Path
import re

TEXT_SAMPLE_BYTES = 4096


def _find_skill_root(start: Path) -> Path:
    for parent in (start, *start.parents):
        if (parent / "SKILL.md").is_file() and (parent / "packager.py").is_file():
            return parent
    raise RuntimeError(f"failed to locate capafy-publisher skill root from {start}")


_SKILL_ROOT = _find_skill_root(Path(__file__).resolve())
PUBLISHER_ROOT_PATH = _SKILL_ROOT
SKILL_CONFIG_PATH = _SKILL_ROOT / "config.json"
DEVELOPER_WORK_DIR_PATH = _SKILL_ROOT / ".temp"
DEVELOPER_FALLBACK_DIR_PATH = _SKILL_ROOT / ".temp-fallback"
DEFAULT_STAGING_PATH = str(DEVELOPER_WORK_DIR_PATH / "staging")
DEFAULT_BUNDLE_PATH = str(DEVELOPER_WORK_DIR_PATH / "bundle.zip")
OPENAI_OFFICIAL_URL_V1 = "https://api.openai.com/v1"
ANTHROPIC_OFFICIAL_URL = "https://api.anthropic.com"
GOOGLE_OFFICIAL_URL = "https://generativelanguage.googleapis.com"
VIRTUALENV_MARKER_FILES = ("pyvenv.cfg",)
VIRTUALENV_BIN_DIRS = ("bin", "Scripts")
DEPENDENCY_MANIFEST_FILES = {
    "requirements.txt",
    "pyproject.toml",
    "poetry.lock",
    "uv.lock",
    "Pipfile",
    "Pipfile.lock",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "environment.yml",
    "environment.yaml",
}
TEXT_ENCODINGS = ("utf-8", "utf-8-sig", "latin-1")

DSN_VALUE_PATTERN = re.compile(r"^(?:jdbc:)?(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|amqp|kafka|sqlserver|oracle)://.+", re.IGNORECASE)
APP_IDENTIFIER_PATTERNS = [
    re.compile(r"^cli_[A-Za-z0-9]{8,}$"),
    re.compile(r"^[0-9]{8,32}$"),
]
AUTH_SCHEME_PATTERN = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_-]*)\s+(.+?)\s*$")
SSH_PUBLIC_KEY_PATTERN = re.compile(
    r"(?:ssh|ecdsa|sk-ssh|sk-ecdsa)-[A-Za-z0-9@._+-]+ AAAA[^\s]+"
)
PII_PATTERNS = [
    re.compile(r"[a-zA-Z0-9._%+\-]{1,64}@(?:[a-zA-Z0-9-]{1,63}\.){1,10}[a-zA-Z]{2,63}"),
    re.compile(r"(\+?\d{1,3}[\s\-])?\(?\d{3}\)?[\s\-]\d{3}[\s\-]\d{4}"),
    re.compile(r"192\.168\.\d+\.\d+"),
    re.compile(r"10\.\d+\.\d+\.\d+"),
    re.compile(r"172\.(1[6-9]|2\d|3[01])\.\d+\.\d+"),
    re.compile(r"\b[A-Z]:[\\/]+(?:Users|Documents and Settings)[\\/]+[^\\/\s]+", re.IGNORECASE),
    re.compile(r"/home/[^\s/]+"),
    re.compile(r"/Users/[^\s/]+"),
    SSH_PUBLIC_KEY_PATTERN,
]

ENV_REF_PATTERN = re.compile(
    r"""os\.environ\[['"]([A-Z][A-Z0-9_]*)['"]\]|"""
    r"""os\.environ\.get\(['"]([A-Z][A-Z0-9_]*)['"](?:\s*,\s*[^)]*)?\)|"""
    r"""os\.getenv\(['"]([A-Z][A-Z0-9_]*)['"](?:\s*,\s*[^)]*)?\)|"""
    r"""getenv\(['"]([A-Z][A-Z0-9_]*)['"](?:\s*,\s*[^)]*)?\)|"""
    r"""process\.env(?:\?\.|\.)([A-Z][A-Z0-9_]*)|"""
    r"""process\.env\[['"]([A-Z][A-Z0-9_]*)['"]\]|"""
    r"""import\.meta\.env(?:\?\.|\.)([A-Z][A-Z0-9_]*)|"""
    r"""import\.meta\.env\[['"]([A-Z][A-Z0-9_]*)['"]\]|"""
    r"""(?:\$\{([A-Z][A-Z0-9_]*)\}|\$([A-Z][A-Z0-9_]*))"""
)
STRUCTURED_ASSIGNMENT_PATTERNS = [
    re.compile(r"""^\s*(?:export\s+)?(?P<key>[A-Za-z_][A-Za-z0-9_.-]{1,120})\s*=\s*(?P<value>.+?)\s*$"""),
    re.compile(r"""^\s*['"]?(?P<key>[A-Za-z_][A-Za-z0-9_.-]{1,120})['"]?\s*:\s*(?P<value>.+?)\s*$"""),
]


__all__ = [
    "ANTHROPIC_OFFICIAL_URL",
    "APP_IDENTIFIER_PATTERNS",
    "AUTH_SCHEME_PATTERN",
    "DEFAULT_BUNDLE_PATH",
    "DEVELOPER_FALLBACK_DIR_PATH",
    "DEFAULT_STAGING_PATH",
    "DEPENDENCY_MANIFEST_FILES",
    "DEVELOPER_WORK_DIR_PATH",
    "DSN_VALUE_PATTERN",
    "ENV_REF_PATTERN",
    "GOOGLE_OFFICIAL_URL",
    "OPENAI_OFFICIAL_URL_V1",
    "PII_PATTERNS",
    "PUBLISHER_ROOT_PATH",
    "SKILL_CONFIG_PATH",
    "SSH_PUBLIC_KEY_PATTERN",
    "STRUCTURED_ASSIGNMENT_PATTERNS",
    "TEXT_ENCODINGS",
    "TEXT_SAMPLE_BYTES",
    "VIRTUALENV_BIN_DIRS",
    "VIRTUALENV_MARKER_FILES",
]
