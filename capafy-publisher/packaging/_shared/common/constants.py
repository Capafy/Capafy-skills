from __future__ import annotations

from pathlib import Path
import re

PLACEHOLDER = "PLATFORM_MANAGED_KEY"
TEXT_SAMPLE_BYTES = 4096


def _find_skill_root(start: Path) -> Path:
    for parent in (start, *start.parents):
        if (parent / "SKILL.md").is_file() and (parent / "packager.py").is_file():
            return parent
    raise RuntimeError(f"failed to locate capafy-publisher skill root from {start}")


_SKILL_ROOT = _find_skill_root(Path(__file__).resolve())
SKILL_CONFIG_PATH = _SKILL_ROOT / "config.json"
DEVELOPER_WORK_DIR_PATH = _SKILL_ROOT / ".temp"
DEVELOPER_FALLBACK_DIR_PATH = _SKILL_ROOT / ".temp-fallback"
DEFAULT_STAGING_PATH = str(DEVELOPER_WORK_DIR_PATH / "staging")
DEFAULT_BUNDLE_PATH = str(DEVELOPER_WORK_DIR_PATH / "bundle.zip")
OPENAI_OFFICIAL_URL_V1 = "https://api.openai.com/v1"
ANTHROPIC_OFFICIAL_URL = "https://api.anthropic.com"
GOOGLE_OFFICIAL_URL = "https://generativelanguage.googleapis.com"
WORKSPACE_DOCUMENTS_MANIFEST_NAME = "agent.workspace_documents.json"
_RUNTIME_EXCLUDED_DIRS = {"node_modules", ".venv", "venv"}
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
VERSION_COMMANDS = {
    "python3": ["python3", "--version"],
    "pip": ["python3", "-m", "pip", "--version"],
    "node": ["node", "--version"],
    "npm": ["npm", "--version"],
    "uv": ["uv", "--version"],
    "git": ["git", "--version"],
}
SYSTEM_COMPONENT_COMMANDS = {
    "bash": ["bash", "--version"],
    "curl": ["curl", "--version"],
    "ffmpeg": ["ffmpeg", "-version"],
    "sqlite3": ["sqlite3", "--version"],
    "chromium": ["chromium", "--version"],
    "google-chrome": ["google-chrome", "--version"],
    "playwright": ["playwright", "--version"],
}
SYSTEM_PACKAGE_CANDIDATES = {
    "apt": [
        "python3",
        "python3-venv",
        "git",
        "curl",
        "ffmpeg",
        "sqlite3",
        "nodejs",
        "npm",
        "chromium",
        "chromium-browser",
    ],
    "brew": [
        "python@3",
        "git",
        "curl",
        "ffmpeg",
        "sqlite",
        "node",
        "chromium",
    ],
    "winget": [
        "Python.Python.3",
        "Git.Git",
        "cURL.cURL",
        "Gyan.FFmpeg",
        "SQLite.SQLite",
        "OpenJS.NodeJS",
        "Google.Chrome",
    ],
    "choco": [
        "python",
        "git",
        "curl",
        "ffmpeg",
        "sqlite",
        "nodejs",
        "googlechrome",
    ],
    "scoop": [
        "python",
        "git",
        "curl",
        "ffmpeg",
        "sqlite",
        "nodejs",
        "googlechrome",
    ],
    "dnf": [
        "python3",
        "git",
        "curl",
        "ffmpeg",
        "sqlite",
        "nodejs",
        "npm",
        "chromium",
    ],
    "yum": [
        "python3",
        "git",
        "curl",
        "ffmpeg",
        "sqlite",
        "nodejs",
        "npm",
        "chromium",
    ],
    "rpm": [
        "python3",
        "git",
        "curl",
        "ffmpeg",
        "sqlite",
        "nodejs",
        "npm",
        "chromium",
    ],
    "apk": [
        "python3",
        "git",
        "curl",
        "ffmpeg",
        "sqlite",
        "nodejs",
        "npm",
        "chromium",
    ],
    "pacman": [
        "python",
        "git",
        "curl",
        "ffmpeg",
        "sqlite",
        "nodejs",
        "npm",
        "chromium",
    ],
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
    re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
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
    "WORKSPACE_DOCUMENTS_MANIFEST_NAME",
    "OPENAI_OFFICIAL_URL_V1",
    "PII_PATTERNS",
    "PLACEHOLDER",
    "SKILL_CONFIG_PATH",
    "SSH_PUBLIC_KEY_PATTERN",
    "STRUCTURED_ASSIGNMENT_PATTERNS",
    "SYSTEM_COMPONENT_COMMANDS",
    "SYSTEM_PACKAGE_CANDIDATES",
    "TEXT_ENCODINGS",
    "TEXT_SAMPLE_BYTES",
    "VERSION_COMMANDS",
    "VIRTUALENV_BIN_DIRS",
    "VIRTUALENV_MARKER_FILES",
]
