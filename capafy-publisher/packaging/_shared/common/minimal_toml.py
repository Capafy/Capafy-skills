from __future__ import annotations

import ast
import re
from typing import Any


class MinimalTOMLDecodeError(ValueError):
    pass



_BARE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

_INTEGER_PATTERN = re.compile(r"^[+-]?\d+$")

_FLOAT_PATTERN = re.compile(r"^[+-]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][+-]?\d+)?$")


def _strip_comment(line: str) -> str:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(line):
        if quote == '"':
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                quote = None
            continue
        if quote == "'":
            if char == "'":
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char == "#":
            return line[:index].rstrip()
    return line.rstrip()


def _split_unquoted(value: str, separator: str) -> list[str]:
    parts: list[str] = []
    start = 0
    quote: str | None = None
    escaped = False
    depth = 0
    for index, char in enumerate(value):
        if quote == '"':
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                quote = None
            continue
        if quote == "'":
            if char == "'":
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char == "[":
            depth += 1
            continue
        if char == "]":
            depth -= 1
            if depth < 0:
                raise MinimalTOMLDecodeError("unexpected closing bracket")
            continue
        if char == separator and depth == 0:
            parts.append(value[start:index].strip())
            start = index + 1
    if quote is not None:
        raise MinimalTOMLDecodeError("unterminated string")
    if depth:
        raise MinimalTOMLDecodeError("unterminated array")
    parts.append(value[start:].strip())
    return parts


def _parse_basic_string(value: str) -> str:
    try:
        parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError) as exc:
        raise MinimalTOMLDecodeError(f"invalid string: {value}") from exc
    if not isinstance(parsed, str):
        raise MinimalTOMLDecodeError(f"invalid string: {value}")
    return parsed


def _parse_literal_string(value: str) -> str:
    if len(value) < 2 or value[-1] != "'":
        raise MinimalTOMLDecodeError(f"invalid literal string: {value}")
    return value[1:-1]


def _parse_array(value: str) -> list[Any]:
    if not value.endswith("]"):
        raise MinimalTOMLDecodeError(f"invalid array: {value}")
    inner = value[1:-1].strip()
    if not inner:
        return []
    return [_parse_value(part) for part in _split_unquoted(inner, ",") if part]


def _parse_value(value: str) -> Any:
    normalized = value.strip()
    if not normalized:
        raise MinimalTOMLDecodeError("empty value")
    if normalized.startswith('"'):
        return _parse_basic_string(normalized)
    if normalized.startswith("'"):
        return _parse_literal_string(normalized)
    lowered = normalized.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if normalized.startswith("["):
        return _parse_array(normalized)
    if _INTEGER_PATTERN.match(normalized):
        return int(normalized.replace("_", ""))
    if _FLOAT_PATTERN.match(normalized):
        return float(normalized.replace("_", ""))
    raise MinimalTOMLDecodeError(f"unsupported value: {value}")


def _parse_key_path(raw_key: str) -> list[str]:
    parts = _split_unquoted(raw_key.strip(), ".")
    if not parts or any(not part for part in parts):
        raise MinimalTOMLDecodeError(f"invalid key: {raw_key}")
    parsed: list[str] = []
    for part in parts:
        if part.startswith('"'):
            parsed.append(_parse_basic_string(part))
        elif part.startswith("'"):
            parsed.append(_parse_literal_string(part))
        elif _BARE_KEY_PATTERN.match(part):
            parsed.append(part)
        else:
            raise MinimalTOMLDecodeError(f"invalid key: {raw_key}")
    return parsed


def _descend(root: dict[str, Any], path: list[str]) -> dict[str, Any]:
    current = root
    for part in path:
        existing = current.setdefault(part, {})
        if not isinstance(existing, dict):
            raise MinimalTOMLDecodeError(f"key is not a table: {part}")
        current = existing
    return current


def _assign(table: dict[str, Any], key_path: list[str], value: Any) -> None:
    target = _descend(table, key_path[:-1])
    key = key_path[-1]
    if key in target:
        raise MinimalTOMLDecodeError(f"duplicate key: {'.'.join(key_path)}")
    target[key] = value


def loads(text: str | bytes) -> dict[str, Any]:
    source = text.decode("utf-8") if isinstance(text, bytes) else str(text)
    root: dict[str, Any] = {}
    current_table = root

    for line_number, raw_line in enumerate(source.splitlines(), start=1):
        line = _strip_comment(raw_line).strip()
        if not line:
            continue
        if line.startswith("["):
            if not line.endswith("]") or line.startswith("[["):
                raise MinimalTOMLDecodeError(f"invalid table header on line {line_number}")
            key_path = _parse_key_path(line[1:-1])
            current_table = _descend(root, key_path)
            continue
        key_text, separator, value_text = line.partition("=")
        if not separator:
            raise MinimalTOMLDecodeError(f"invalid assignment on line {line_number}")
        key_path = _parse_key_path(key_text)
        value = _parse_value(value_text)
        _assign(current_table, key_path, value)

    return root



TOMLDecodeError = MinimalTOMLDecodeError


__all__ = ["MinimalTOMLDecodeError", "TOMLDecodeError", "loads"]
