from __future__ import annotations
from typing import Optional

import hashlib

from packaging._shared.common.local_path_detection import LOCAL_PATH_PLACEHOLDER


def split_value_suffix(raw_value: str) -> tuple[str, str]:
    trimmed = raw_value.rstrip()
    suffix = raw_value[len(trimmed) :]
    in_quote: Optional[str] = None
    escaped = False
    comment_index: Optional[int] = None
    for index, char in enumerate(trimmed):
        if in_quote is not None:
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == in_quote:
                in_quote = None
            continue
        if char in {"'", '"'}:
            in_quote = char
            continue
        if char == "#":
            comment_index = index
            break

    if comment_index is not None:
        suffix = trimmed[comment_index:] + suffix
        trimmed = trimmed[:comment_index].rstrip()

    while trimmed.endswith((",", ";")):
        suffix = trimmed[-1] + suffix
        trimmed = trimmed[:-1].rstrip()
    return trimmed, suffix


def placeholder_literal(raw_value: str, placeholder: str) -> str:
    core, suffix = split_value_suffix(raw_value)
    if len(core) >= 2 and core[0] == core[-1] and core[0] in {"'", '"'}:
        quote = core[0]
        return f"{quote}{placeholder}{quote}{suffix}"
    return f"{placeholder}{suffix}"


def stable_local_placeholder(value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8].upper()
    return f"{LOCAL_PATH_PLACEHOLDER}_{digest}"


def split_raw_line(raw_line: str) -> tuple[str, str]:
    if raw_line.endswith("\r\n"):
        return raw_line[:-2], "\r\n"
    if raw_line.endswith("\n"):
        return raw_line[:-1], "\n"
    return raw_line, ""


__all__ = [
    "placeholder_literal",
    "split_raw_line",
    "split_value_suffix",
    "stable_local_placeholder",
]
