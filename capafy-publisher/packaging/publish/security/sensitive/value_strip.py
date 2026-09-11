from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional

from packaging.common.fs import (
    iter_workspace_files,
    read_text,
    relpath,
)
from packaging.common.text_parse import looks_like_platform_managed_placeholder_value


def _iter_text_files(root: Path) -> Iterable[tuple[Path, str, str]]:
    for path in iter_workspace_files(root, skip_system=False):
        if path.is_symlink() or not path.is_file():
            continue
        text, encoding = read_text(path)
        if text is None or encoding is None:
            continue
        yield path, text, encoding


def _strip_candidates(key_value: str, extra_candidates: Optional[Iterable[str]] = None) -> list[str]:
    candidates: list[str] = []

    def add(candidate: str) -> None:
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    add(key_value)
    for encoded in (
        json.dumps(key_value, ensure_ascii=False)[1:-1],
        json.dumps(key_value, ensure_ascii=True)[1:-1],
    ):
        add(encoded)
        add(encoded.replace("/", "\\/"))
    if extra_candidates is not None:
        for extra_candidate in extra_candidates:
            add(str(extra_candidate))
    return candidates


def _replace_json_scalar_values(
    text: str,
    key_value: str,
    replacement: str,
) -> Optional[tuple[str, int]]:
    """Replace exact JSON scalar values while preserving valid JSON syntax."""
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return None

    replacements = 0

    def visit(node: object) -> object:
        nonlocal replacements
        if isinstance(node, dict):
            return {key: visit(value) for key, value in node.items()}
        if isinstance(node, list):
            return [visit(value) for value in node]
        if node == key_value or (
            isinstance(node, (int, float))
            and not isinstance(node, bool)
            and str(node) == key_value
        ):
            replacements += 1
            return replacement
        return node

    updated_payload = visit(payload)
    if not replacements:
        return text, 0
    return json.dumps(updated_payload, ensure_ascii=False, indent=2) + "\n", replacements


def strip_value_from_staging(
    staging_root: Path,
    key_value: str,
    placeholder: str,
    *,
    extra_candidates: Optional[Iterable[str]] = None,
    allow_empty_placeholder: bool = False,
) -> dict:
    if not placeholder and not allow_empty_placeholder:
        raise ValueError("strip must receive placeholder explicitly")
    if looks_like_platform_managed_placeholder_value(key_value):
        return {
            "placeholder": placeholder,
            "replaced_in": [],
            "total_replacements": 0,
            "skipped": "placeholder_value",
        }

    replacement = placeholder
    candidates = _strip_candidates(key_value, extra_candidates=extra_candidates)
    replaced_in: list[str] = []
    total_replacements = 0
    for path, text, encoding in _iter_text_files(staging_root):
        if path.suffix.lower() in {".json", ".jsonc"}:
            json_result = _replace_json_scalar_values(text, key_value, replacement)
            if json_result is not None:
                updated_json, occurrences = json_result
                if occurrences:
                    path.write_text(updated_json, encoding=encoding)
                    replaced_in.append(relpath(path, staging_root))
                    total_replacements += occurrences
                continue

        updated_text = text
        occurrences = 0
        for candidate in candidates:
            if candidate == replacement:
                continue

            count = updated_text.count(candidate)
            if not count:
                continue
            updated_text = updated_text.replace(candidate, replacement)
            occurrences += count
        if not occurrences:
            continue
        path.write_text(updated_text, encoding=encoding)
        replaced_in.append(relpath(path, staging_root))
        total_replacements += occurrences

    return {
        "placeholder": replacement,
        "replaced_in": replaced_in,
        "total_replacements": total_replacements,
    }


__all__ = ["strip_value_from_staging"]
