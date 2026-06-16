from __future__ import annotations
from typing import Any, Iterable, Optional

try:
    import yaml
except ImportError as exc:  # pragma: no cover - depends on host environment
    yaml = None
    _YAML_IMPORT_ERROR = exc
else:
    _YAML_IMPORT_ERROR = None


def _require_yaml():
    if yaml is None:
        raise RuntimeError("YAML configuration support requires PyYAML") from _YAML_IMPORT_ERROR
    return yaml


def safe_yaml_loads(text: str) -> Any:
    parser = _require_yaml()
    try:
        payload = parser.safe_load(text) or {}
    except Exception as exc:
        yaml_error = getattr(parser, "YAMLError", ())
        if yaml_error and isinstance(exc, yaml_error):
            raise ValueError(f"failed to parse YAML: {exc}") from exc
        raise
    return payload


def safe_yaml_mapping_loads(text: str, *, label: str = "YAML document") -> dict:
    payload = safe_yaml_loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a YAML mapping")
    return payload


def safe_yaml_dumps(data: dict) -> str:
    parser = _require_yaml()
    return parser.safe_dump(data, sort_keys=False, allow_unicode=True)


def _parse_list_part(part: str) -> tuple[str, Optional[int]]:
    normalized = str(part or "").strip()
    if normalized.endswith("]") and "[" in normalized:
        key, raw_index = normalized[:-1].rsplit("[", 1)
        try:
            return key, int(raw_index)
        except ValueError:
            return normalized, None
    return normalized, None


def _child_for_part(node: Any, part: str) -> Any:
    key, index = _parse_list_part(part)
    if index is None:
        if isinstance(node, dict):
            return node.get(key)
        return None
    if not isinstance(node, dict):
        return None
    values = node.get(key)
    if isinstance(values, str):
        items = [item.strip() for item in values.split(",") if item.strip()]
        if index < 0 or index >= len(items):
            return None
        return items[index]
    if not isinstance(values, list) or index < 0 or index >= len(values):
        return None
    return values[index]


def _child_for_tree_path_part(node: Any, part: str) -> Any:
    key, index = _parse_list_part(part)
    if isinstance(node, list):
        try:
            list_index = int(part)
        except ValueError:
            return None
        return node[list_index] if 0 <= list_index < len(node) else None
    if not isinstance(node, dict):
        return None
    if index is None:
        return node.get(key)
    values = node.get(key)
    if isinstance(values, list) and 0 <= index < len(values):
        return values[index]
    return None


def _parent_for_tree_path(payload: object, key_path: Iterable[str]) -> tuple[Optional[dict], str]:
    parts = [str(part or "").strip() for part in key_path if str(part or "").strip()]
    if not parts:
        return None, ""
    node: Any = payload
    for part in parts[:-1]:
        node = _child_for_tree_path_part(node, part)
        if node is None:
            return None, ""
    return (node, parts[-1]) if isinstance(node, dict) else (None, "")


def find_yaml_string_leaf_path(payload: object, needle: str) -> list[str]:
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


def remove_yaml_object_key_at_path(payload: object, key_path: Iterable[str]) -> bool:
    parent, key = _parent_for_tree_path(payload, key_path)
    if parent is None or not key or key not in parent:
        return False
    del parent[key]
    return True


def remove_yaml_object_key_containing_string(payload: object, needle: str) -> bool:
    key_path = find_yaml_string_leaf_path(payload, needle)
    if not key_path:
        return False
    return remove_yaml_object_key_at_path(payload, key_path)


def get_yaml_path_value(payload: dict, key_path: Iterable[str]) -> Any:
    node: Any = payload
    for part in [str(part or "").strip() for part in key_path if str(part or "").strip()]:
        node = _child_for_part(node, part)
        if node is None:
            return None
    return node


def set_yaml_path_value(payload: dict, key_path: Iterable[str], value: Any) -> bool:
    parts = [str(part or "").strip() for part in key_path if str(part or "").strip()]
    if not parts:
        return False
    node: Any = payload
    for part in parts[:-1]:
        key, index = _parse_list_part(part)
        if index is None:
            if isinstance(node, dict):
                existing = node.get(key)
                if existing is None:
                    node[key] = {}
                elif not isinstance(existing, dict):
                    return False
                node = node[key]
                continue
            return False
        if isinstance(node, dict):
            values = node.get(key)
            if not isinstance(values, list) or index < 0 or index >= len(values):
                return False
            if not isinstance(values[index], dict):
                values[index] = {}
            node = values[index]
            continue
        return False
    if not isinstance(node, dict):
        return False
    last, index = _parse_list_part(parts[-1])
    if index is not None:
        values = node.get(last)
        if isinstance(values, str):
            values = [item.strip() for item in values.split(",") if item.strip()]
            node[last] = values
        if not isinstance(values, list) or index < 0 or index >= len(values):
            return False
        if values[index] == value:
            return False
        values[index] = value
        return True
    if node.get(last) == value:
        return False
    node[last] = value
    return True


__all__ = [
    "find_yaml_string_leaf_path",
    "get_yaml_path_value",
    "remove_yaml_object_key_at_path",
    "remove_yaml_object_key_containing_string",
    "safe_yaml_dumps",
    "safe_yaml_loads",
    "safe_yaml_mapping_loads",
    "set_yaml_path_value",
]
