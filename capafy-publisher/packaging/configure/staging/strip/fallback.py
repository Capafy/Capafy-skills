from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from packaging.configure.contracts import ReviewedScanBuildInput
from packaging.configure.staging.strip.targets import StripTarget, collect_reviewed_scan_input_strip_targets


@dataclass(frozen=True)
class StripSummary:
    total_replacements: int
    targets_matched: int


def replace_values_in_staging(
    staging_root: Path,
    replacements: list[tuple[str, str]],
    *,
    scan_only_prefix: str = "_scan_only",
) -> StripSummary:
    targets = [
        StripTarget(value=value, placeholder=placeholder)
        for value, placeholder in replacements
        if value
    ]
    if not targets:
        return StripSummary(total_replacements=0, targets_matched=0)

    total = 0
    matched = 0
    for file_path in _text_files(staging_root, scan_only_prefix):
        try:
            text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        updated = text
        file_replaced = 0
        for target in targets:
            count = updated.count(target.value)
            if count > 0:
                updated = updated.replace(target.value, target.placeholder)
                file_replaced += count

        if file_replaced > 0:
            file_path.write_text(updated, encoding="utf-8")
            total += file_replaced
            matched += 1

    return StripSummary(total_replacements=total, targets_matched=matched)


def collect_strip_targets(reviewed_scan_input: ReviewedScanBuildInput) -> list[StripTarget]:
    return collect_reviewed_scan_input_strip_targets(reviewed_scan_input)


def apply_strip(
    staging_root: Path,
    reviewed_scan_input: ReviewedScanBuildInput,
    *,
    scan_only_prefix: str = "_scan_only",
) -> StripSummary:
    targets = collect_strip_targets(reviewed_scan_input)
    if not targets:
        return StripSummary(total_replacements=0, targets_matched=0)
    return replace_values_in_staging(
        staging_root,
        [(target.value, target.placeholder) for target in targets],
        scan_only_prefix=scan_only_prefix,
    )


def _text_files(staging_root: Path, scan_only_prefix: str) -> list[Path]:
    result: list[Path] = []
    if not staging_root.is_dir():
        return result
    for path in staging_root.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(staging_root).as_posix()
        except ValueError:
            continue
        if rel.startswith(scan_only_prefix):
            continue

        if path.suffix.lower() in {".zip", ".tar", ".gz", ".bz2", ".xz",
                                     ".png", ".jpg", ".jpeg", ".gif", ".ico",
                                     ".woff", ".woff2", ".ttf", ".eot",
                                     ".pyc", ".pyo", ".so", ".dll", ".dylib",
                                     ".exe", ".bin", ".dat"}:
            continue
        result.append(path)
    return result


__all__ = ["StripSummary", "apply_strip", "collect_strip_targets", "replace_values_in_staging"]
