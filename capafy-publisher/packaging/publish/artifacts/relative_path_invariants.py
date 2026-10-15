from __future__ import annotations

import re
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from typing import Iterator, Optional
from urllib.parse import unquote

from packaging.common.final_zip_files import collect_final_zip_entries
from packaging.common.fs import read_text, relpath


_MARKDOWN_SUFFIXES = frozenset({".md", ".markdown", ".mdx"})
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_INLINE_CODE = re.compile(r"(`+).*?\1(?!`)")
_INLINE_LINK = re.compile(
    r"!?\[[^\]\n]*\]\(\s*(?:<(?P<angle>[^>\n]+)>|(?P<plain>[^\s()]+))"
    r"(?:\s+['\"][^\n]*?['\"])?\s*\)"
)
_LINK_DEFINITION = re.compile(
    r"^ {0,3}\[[^\]\n]+\]:\s*(?:<(?P<angle>[^>\n]+)>|(?P<plain>\S+))"
)


def _iter_markdown_relative_links(text: str) -> Iterator[tuple[int, str]]:
    # Only links have a document-relative base. Commands and configuration do not.
    text = re.sub(r"<!--.*?-->", lambda match: "\n" * match.group().count("\n"), text, flags=re.S)
    fence_char = ""
    fence_length = 0
    for line_number, line in enumerate(text.splitlines(), start=1):
        fence = _FENCE.match(line)
        if fence_char:
            if (fence and fence.group(1)[0] == fence_char
                    and len(fence.group(1)) >= fence_length and not fence.group(2).strip()):
                fence_char = ""
            continue
        if fence:
            fence_char = fence.group(1)[0]
            fence_length = len(fence.group(1))
            continue
        if line.startswith(("    ", "\t")):
            continue
        line = _INLINE_CODE.sub("", line)
        matches = list(_INLINE_LINK.finditer(line))
        definition = _LINK_DEFINITION.match(line)
        if definition:
            matches.append(definition)
        for match in matches:
            destination = match.group("angle") or match.group("plain")
            path = unquote(re.split(r"[?#]", destination, maxsplit=1)[0]).replace("\\", "/")
            if path.startswith(("./", "../")):
                yield line_number, path


@dataclass(frozen=True)
class PackageRelativePathViolation:
    relpath: str
    line: int
    reference: str
    reason: str


def _resolve_archive_reference(source: str, reference: str) -> Optional[str]:
    parts = list(PurePosixPath(source).parent.parts)
    normalized = reference.replace("\\", "/").split("#", 1)[0]
    for part in normalized.split("/"):
        if not part or part == ".":
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(part)
    return "/".join(parts)


def _matches_archive_glob(path: str, pattern: str) -> bool:
    # Match whole path segments: * stays in one directory; ** can span directories.
    parts = PurePosixPath(path).parts
    positions = {0}
    for segment in PurePosixPath(pattern).parts:
        if segment == "**":
            positions = set(range(min(positions), len(parts) + 1))
        else:
            positions = {
                index + 1 for index in positions
                if index < len(parts) and fnmatchcase(parts[index], segment)
            }
        if not positions:
            return False
    return len(parts) in positions


def find_packaged_relative_path_violations(staging_root: Path) -> list[PackageRelativePathViolation]:
    entries = collect_final_zip_entries(staging_root)
    # Validate against the installed ZIP layout, including workspace/ flattening.
    archive_paths = set(entries.files_by_archive_path) | set(entries.archive_directories) | {""}
    violations: list[PackageRelativePathViolation] = []
    for archive_path, sources in sorted(entries.files_by_archive_path.items()):
        for source in sources:
            if source.suffix.lower() not in _MARKDOWN_SUFFIXES:
                continue
            text, _encoding = read_text(source)
            if text is None:
                continue
            for line_number, reference in _iter_markdown_relative_links(text):
                resolved = _resolve_archive_reference(archive_path, reference)
                if resolved is None:
                    reason = "escapes package root"
                elif resolved in archive_paths or (
                    any(char in resolved for char in "*?[")
                    and any(_matches_archive_glob(path, resolved) for path in archive_paths)
                ):
                    continue
                else:
                    reason = "target not included in package"
                violations.append(PackageRelativePathViolation(
                    relpath=relpath(source, staging_root),
                    line=line_number,
                    reference=reference,
                    reason=reason,
                ))
    return violations


def validate_packaged_relative_path_references(staging_root: Path) -> None:
    violations = find_packaged_relative_path_violations(staging_root)
    if not violations:
        return
    details = "; ".join(
        f"{item.relpath}:{item.line}: {item.reference} ({item.reason})"
        for item in violations[:5]
    )
    suffix = "" if len(violations) <= 5 else f"; +{len(violations) - 5} more"
    raise ValueError(f"packaged bundle contains invalid relative references: {details}{suffix}")


__all__ = [
    "PackageRelativePathViolation",
    "find_packaged_relative_path_violations",
    "validate_packaged_relative_path_references",
]
