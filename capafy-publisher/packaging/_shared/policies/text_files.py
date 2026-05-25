from __future__ import annotations

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


__all__ = [
    "TEXT_FILE_BASENAMES",
    "TEXT_FILE_SUFFIXES",
]
