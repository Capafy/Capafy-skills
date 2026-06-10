from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple


_JSON_DECODER = json.JSONDecoder()
JsonStringHandler = Callable[[str, Optional[str]], Tuple[str, int]]
JsonStringLeaf = Tuple[List[str], str, str]


def load_json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_json_object(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clone_json_value(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): clone_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clone_json_value(item) for item in value]
    return value


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


def find_json_string_leaf_path(payload: object, needle: str) -> list[str]:
    target = str(needle or "").strip()
    if not target:
        return []
    stack: list[tuple[object, list[str]]] = [(payload, [])]
    while stack:
        node, path_parts = stack.pop()
        if isinstance(node, dict):
            for key, value in node.items():
                child_path = [*path_parts, str(key)]
                if isinstance(value, str) and target in value:
                    return child_path
                if isinstance(value, (dict, list)):
                    stack.append((value, child_path))
            continue
        if isinstance(node, list):
            for index, item in enumerate(node):
                child_path = [*path_parts, str(index)]
                if isinstance(item, str) and target in item:
                    return child_path
                if isinstance(item, (dict, list)):
                    stack.append((item, child_path))
    return []


def json_pointer_parts(pointer: str) -> list[str]:
    return [
        part.replace("~1", "/").replace("~0", "~")
        for part in str(pointer or "").split("/")
        if part
    ]


def find_json_string_value_span(text: str, pointer: str, expected_value: str) -> Optional[tuple[int, int]]:
    parts = json_pointer_parts(pointer)
    if not parts:
        return None
    try:
        return _locate_json_value(text, _skip_json_ws(text, 0), parts, expected_value)
    except (json.JSONDecodeError, IndexError, ValueError):
        return None


def replace_json_value_text(text: str, pointer: str, replacement: object) -> str:
    parts = json_pointer_parts(pointer)
    if not parts:
        return text
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text

    parent = _parent_for_json_path(payload, parts)
    node, key = parent
    if node is None or not key:
        return text
    node[key] = replacement
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def upsert_json_value_file(path: Path, *, pointer: str = "", field: str = "", value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        text = path.read_text(encoding="utf-8") if path.is_file() else "{}"
        payload = json.loads(text)
    except (OSError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    parts = json_pointer_parts(pointer)
    if parts:
        node: dict[str, Any] = payload
        for part in parts[:-1]:
            existing = node.get(part)
            if not isinstance(existing, dict):
                existing = {}
                node[part] = existing
            node = existing
        node[parts[-1]] = value
    else:
        field_name = str(field or "").strip()
        if not field_name:
            return
        payload[field_name] = value

    write_json_object(path, payload)


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


def _child_for_json_path_part(node: object, part: str) -> object:
    if isinstance(node, dict):
        return node.get(part)
    if isinstance(node, list):
        try:
            index = int(part)
        except ValueError:
            return None
        return node[index] if 0 <= index < len(node) else None
    return None


def _parent_for_json_path(payload: object, path_parts: list[str]) -> tuple[Optional[dict], str]:
    if not path_parts:
        return None, ""
    node: Any = payload
    for part in path_parts[:-1]:
        node = _child_for_json_path_part(node, part)
        if node is None:
            return None, ""
    return (node, path_parts[-1]) if isinstance(node, dict) else (None, "")


def remove_json_object_key_at_path(payload: object, path_parts: list[str]) -> bool:
    parent, key = _parent_for_json_path(payload, path_parts)
    if parent is None or not key or key not in parent:
        return False
    del parent[key]
    return True


def remove_json_object_key_containing_string(payload: object, needle: str) -> bool:
    path_parts = find_json_string_leaf_path(payload, needle)
    if not path_parts:
        return False
    return remove_json_object_key_at_path(payload, path_parts)


def remove_json_file_object_key_containing_string(path: Path, needle: str) -> bool:
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    if not remove_json_object_key_containing_string(payload, needle):
        return False
    write_json_object(path, payload)
    return True


__all__ = [
    "JsonStringHandler",
    "JsonStringLeaf",
    "clone_json_value",
    "find_json_string_leaf_path",
    "find_json_string_value_span",
    "iter_json_string_leaves",
    "json_pointer_parts",
    "load_json_object",
    "remove_json_file_object_key_containing_string",
    "remove_json_object_key_at_path",
    "remove_json_object_key_containing_string",
    "replace_json_value_text",
    "upsert_json_value_file",
    "walk_json_strings",
    "write_json_object",
]
