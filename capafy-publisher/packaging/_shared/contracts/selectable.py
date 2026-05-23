from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
from urllib.parse import unquote

from packaging._shared.common.fs import is_archive_artifact







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


SKILL_REFERENCE_SKIP_FILES = {
    "agent.runtime_dependencies.json",
    "agent.runtime_environment.json",
    "system",
    "tools",
    "npm_global_packages",
    "system_packages",
}

SKILL_REFERENCE_NOISE_DIR_NAMES = {
    ".research",
    ".serena",
    "eval",
    "temp",
}


def is_instruction_doc(relpath: str) -> bool:
    name = PurePosixPath(relpath).name
    lowered = name.lower()
    if name in INSTRUCTION_DOC_BASENAMES:
        return True
    return lowered.endswith(INSTRUCTION_DOC_SUFFIXES)


def _should_skip_skill_reference_scan(relpath: str) -> bool:
    name = PurePosixPath(relpath).name
    if name in SKILL_REFERENCE_SKIP_FILES:
        return True
    return is_archive_artifact(relpath)


def should_skip_skill_reference_document(relpath: str) -> bool:
    if _should_skip_skill_reference_scan(relpath):
        return True
    lowered_parts = {part.lower() for part in PurePosixPath(relpath).parts}
    return bool(lowered_parts & SKILL_REFERENCE_NOISE_DIR_NAMES)







def _path_security_variants(path: str) -> tuple[str, ...]:
    normalized = normalize_text(path)
    if not normalized:
        return ()

    variants: list[str] = []
    current = normalized
    for _ in range(4):
        if current not in variants:
            variants.append(current)
        decoded = unquote(current)
        if decoded == current:
            break
        current = decoded
    return tuple(variants)


def normalize_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def is_absolute_like_path(path: str) -> bool:
    for normalized in _path_security_variants(path):
        if (
            PurePosixPath(normalized).is_absolute()
            or PureWindowsPath(normalized).is_absolute()
            or normalized.startswith("~")
        ):
            return True
    return False


def has_parent_reference_path(path: str) -> bool:
    return any(
        ".." in PurePosixPath(normalized).parts or ".." in PureWindowsPath(normalized).parts
        for normalized in _path_security_variants(path)
    )


def validate_logical_path(path: object, *, label: str) -> str:
    normalized = str(path or "").strip()
    if normalized and is_absolute_like_path(normalized):
        raise ValueError(f"{label} must be a logical path, not an absolute path")
    if normalized and has_parent_reference_path(normalized):
        raise ValueError(f"{label} must not contain parent directory traversal")
    return normalized


def normalize_display_prefix(display_prefix: str) -> str:
    normalized = PurePosixPath(str(display_prefix or "").rstrip("/")).as_posix()
    return "" if normalized == "." else normalized


def candidate_path_for_logical_path(source_root, display_prefix: str, logical_path: str):
    if has_parent_reference_path(logical_path):
        raise ValueError("logical_path must not contain parent directory traversal")
    normalized_prefix = normalize_display_prefix(display_prefix)
    normalized_logical = PurePosixPath(logical_path.rstrip("/")).as_posix()
    if normalized_prefix:
        if normalized_logical != normalized_prefix and not normalized_logical.startswith(f"{normalized_prefix}/"):
            return None
        suffix = normalized_logical[len(normalized_prefix):].lstrip("/")
    else:
        suffix = normalized_logical
    return source_root / suffix if suffix else source_root
