from __future__ import annotations

from typing import Callable, List, Optional, Tuple


JsonStringHandler = Callable[[str, Optional[str]], Tuple[str, int]]
JsonStringLeaf = Tuple[List[str], str, str]


def walk_json_strings(payload: object, handler: JsonStringHandler) -> tuple[object, int]:
    replacements = 0

    def walk(node: object, key_name: str | None = None) -> object:
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


def iter_json_string_leaves(payload: object, path_parts: list[str] | None = None) -> list[JsonStringLeaf]:
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


__all__ = ["JsonStringHandler", "JsonStringLeaf", "iter_json_string_leaves", "walk_json_strings"]
