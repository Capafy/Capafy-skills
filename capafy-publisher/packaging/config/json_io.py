from __future__ import annotations

import json
from typing import Callable, List, Optional, Tuple


_JSON_DECODER = json.JSONDecoder()
JsonStringHandler = Callable[[str, Optional[str]], Tuple[str, int]]
JsonStringLeaf = Tuple[List[str], str, str]


def walk_json_strings(payload: object, handler: JsonStringHandler) -> tuple[object, int]:
    replacements = 0

    def walk(node: object, key_name: Optional[str] = None) -> object:
        nonlocal replacements
        if isinstance(node, dict):
            return {key: walk(value, str(key)) for key, value in node.items()}
        if isinstance(node, list):
            return [walk(item, key_name) for item in node]
        if isinstance(node, str):
            updated, count = handler(node, key_name)
            replacements += count
            return updated
        return node

    return walk(payload), replacements


def iter_json_string_leaves(payload: object, path_parts: Optional[list[str]] = None) -> list[JsonStringLeaf]:
    current_path = list(path_parts or [])
    leaves: list[JsonStringLeaf] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            child_path = [*current_path, str(key)]
            if isinstance(value, str) and value.strip():
                leaves.append((child_path, str(key), value))
            else:
                leaves.extend(iter_json_string_leaves(value, child_path))
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            leaves.extend(iter_json_string_leaves(item, [*current_path, f"[{index}]"]))
    return leaves


def json_pointer_parts(pointer: str) -> list[str]:
    raw_pointer = str(pointer or "")
    if not raw_pointer:
        return []
    raw_parts = raw_pointer[1:].split("/") if raw_pointer.startswith("/") else raw_pointer.split("/")
    return [
        part.replace("~1", "/").replace("~0", "~")
        for part in raw_parts
    ]


def find_json_string_value_span(text: str, pointer: str, expected_value: str) -> Optional[tuple[int, int]]:
    parts = json_pointer_parts(pointer)
    if not parts:
        return None
    try:
        return _locate_json_value(text, _skip_json_ws(text, 0), parts, expected_value)
    except (json.JSONDecodeError, IndexError, ValueError):
        return None


def _locate_json_value(
    text: str,
    pos: int,
    parts: list[str],
    expected_value: str,
) -> Optional[tuple[int, int]]:
    pos = _skip_json_ws(text, pos)
    if not parts:
        value, end = _JSON_DECODER.raw_decode(text, pos)
        if isinstance(value, str) and value == expected_value:
            return pos, end
        return None
    if pos >= len(text):
        return None
    if text[pos] == "{":
        return _locate_json_object_member(text, pos, parts, expected_value)
    if text[pos] == "[":
        return _locate_json_array_item(text, pos, parts, expected_value)
    return None


def _locate_json_object_member(
    text: str,
    pos: int,
    parts: list[str],
    expected_value: str,
) -> Optional[tuple[int, int]]:
    target_key = parts[0]
    pos = _skip_json_ws(text, pos + 1)
    while pos < len(text) and text[pos] != "}":
        key, key_end = _JSON_DECODER.raw_decode(text, pos)
        if not isinstance(key, str):
            return None
        colon = _skip_json_ws(text, key_end)
        if colon >= len(text) or text[colon] != ":":
            return None
        value_start = _skip_json_ws(text, colon + 1)
        if key == target_key:
            return _locate_json_value(text, value_start, parts[1:], expected_value)
        _value, value_end = _JSON_DECODER.raw_decode(text, value_start)
        pos = _skip_json_ws(text, value_end)
        if pos < len(text) and text[pos] == ",":
            pos = _skip_json_ws(text, pos + 1)
    return None


def _locate_json_array_item(
    text: str,
    pos: int,
    parts: list[str],
    expected_value: str,
) -> Optional[tuple[int, int]]:
    try:
        target_index = int(parts[0])
    except ValueError:
        return None
    pos = _skip_json_ws(text, pos + 1)
    index = 0
    while pos < len(text) and text[pos] != "]":
        if index == target_index:
            return _locate_json_value(text, pos, parts[1:], expected_value)
        _value, value_end = _JSON_DECODER.raw_decode(text, pos)
        pos = _skip_json_ws(text, value_end)
        if pos < len(text) and text[pos] == ",":
            pos = _skip_json_ws(text, pos + 1)
        index += 1
    return None


def _skip_json_ws(text: str, pos: int) -> int:
    while pos < len(text) and text[pos] in " \t\r\n":
        pos += 1
    return pos


__all__ = [
    "JsonStringHandler",
    "JsonStringLeaf",
    "find_json_string_value_span",
    "iter_json_string_leaves",
    "json_pointer_parts",
    "walk_json_strings",
]
