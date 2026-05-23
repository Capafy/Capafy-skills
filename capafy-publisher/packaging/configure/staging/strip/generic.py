from __future__ import annotations

from pathlib import Path

from packaging.configure.contracts import GenericValue
from packaging.configure.sensitive.value_strip import can_safely_replace_literal_globally


def _replace_nth_value(text: str, value: str, placeholder: str, occurrence_index: int) -> str:
    target_occurrence = occurrence_index if occurrence_index > 0 else 1
    start = 0
    seen = 0
    while True:
        index = text.find(value, start)
        if index < 0:
            return text
        seen += 1
        if seen == target_occurrence:
            return f"{text[:index]}{placeholder}{text[index + len(value):]}"
        start = index + len(value)


def apply_generic_to_staging(
    staging_root: Path,
    generic_values: tuple[GenericValue, ...],
) -> None:
    for gv in generic_values:
        if not gv.source_relpath or not gv.original_value:
            continue
        if not can_safely_replace_literal_globally(gv.original_value, gv.value_type):
            continue
        file_path = staging_root / gv.source_relpath
        if not file_path.is_file():
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except OSError:
            continue
        if gv.original_value not in text:
            continue
        updated = _replace_nth_value(
            text,
            gv.original_value,
            gv.placeholder,
            gv.location.occurrence_index_identity(),
        )
        if updated != text:
            file_path.write_text(updated, encoding="utf-8")


__all__ = ["apply_generic_to_staging"]
