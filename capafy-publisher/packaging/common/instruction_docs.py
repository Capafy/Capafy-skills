from __future__ import annotations

from pathlib import PurePosixPath


INSTRUCTION_DOC_BASENAMES = {
    "AGENTS.md",
    "HOOK.md",
    "SKILL.md",
    "CLAUDE.md",
    "README.md",
    "MEMORY.md",
    "TOOLS.md",
    "USER.md",
}
INSTRUCTION_DOC_SUFFIXES = (".md", ".markdown", ".mdx", ".rst", ".txt")


def is_instruction_doc(relpath: str) -> bool:
    name = PurePosixPath(relpath).name
    return name in INSTRUCTION_DOC_BASENAMES or name.lower().endswith(INSTRUCTION_DOC_SUFFIXES)


__all__ = ["INSTRUCTION_DOC_BASENAMES", "INSTRUCTION_DOC_SUFFIXES", "is_instruction_doc"]
