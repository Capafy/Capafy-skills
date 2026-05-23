from __future__ import annotations


def strip_wrapping_quotes(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        return stripped[1:-1].strip()
    return stripped


def strip_inline_comment(value: str) -> str:
    stripped = value.strip()
    if "#" not in stripped:
        return stripped

    in_single = False
    in_double = False
    result: list[str] = []
    for char in stripped:
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            break
        result.append(char)
    return "".join(result).strip()


__all__ = ["strip_inline_comment", "strip_wrapping_quotes"]
