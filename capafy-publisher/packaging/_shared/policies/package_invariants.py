from __future__ import annotations
from typing import Optional

from dataclasses import dataclass
from pathlib import Path

from packaging._shared.common.final_zip_files import collect_final_zip_entries
from packaging._shared.common.fs import read_text
from packaging._shared.common.local_path_detection import looks_like_local_path
from packaging._shared.policies.content_scan import should_skip_content_scan_for_file
from packaging._shared.policies.text_files import TEXT_FILE_BASENAMES, TEXT_FILE_SUFFIXES


@dataclass(frozen=True)
class PackageLocalPathViolation:
    relpath: str
    sample: str


def _should_check_text_file(path: Path) -> bool:
    if should_skip_content_scan_for_file(path.name):
        return False
    return path.name in TEXT_FILE_BASENAMES or path.name.startswith(".env") or path.suffix.lower() in TEXT_FILE_SUFFIXES


def _sample_local_path(text: str) -> str:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if looks_like_local_path(line):
            return line[:240]
    return ""


def find_packaged_local_path_violations(
    staging_root: Path,
    *,
    exclude_paths: Optional[set[str]] = None,
    exclude_prefixes: tuple[str, ...] = (),
) -> list[PackageLocalPathViolation]:
    entries = collect_final_zip_entries(
        staging_root,
        exclude_paths=exclude_paths,
        exclude_prefixes=exclude_prefixes,
    )
    violations: list[PackageLocalPathViolation] = []
    seen_relpaths: set[str] = set()
    for relpath in sorted(entries.staging_file_relpaths):
        if relpath in seen_relpaths:
            continue
        path = staging_root / relpath
        if not _should_check_text_file(path):
            continue
        text, _encoding = read_text(path)
        if text is None:
            continue
        sample = _sample_local_path(text)
        if not sample:
            continue
        seen_relpaths.add(relpath)
        violations.append(PackageLocalPathViolation(relpath=relpath, sample=sample))
    return violations


def validate_no_packaged_local_path_violations(
    staging_root: Path,
    *,
    exclude_paths: Optional[set[str]] = None,
    exclude_prefixes: tuple[str, ...] = (),
) -> None:
    violations = find_packaged_local_path_violations(
        staging_root,
        exclude_paths=exclude_paths,
        exclude_prefixes=exclude_prefixes,
    )
    if not violations:
        return
    details = "; ".join(
        f"{item.relpath}: {item.sample}"
        for item in violations[:5]
    )
    suffix = "" if len(violations) <= 5 else f"; +{len(violations) - 5} more"
    raise ValueError(f"packaged bundle still contains creator-local paths: {details}{suffix}")


__all__ = [
    "PackageLocalPathViolation",
    "find_packaged_local_path_violations",
    "validate_no_packaged_local_path_violations",
]
