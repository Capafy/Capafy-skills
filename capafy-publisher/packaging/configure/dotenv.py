from __future__ import annotations

from collections.abc import Collection, Iterator
import re


_ENV_LINE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


def unquote_dotenv_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value.strip()


def iter_dotenv_assignments(text: str) -> Iterator[tuple[str, str, int]]:
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _ENV_LINE.match(line)
        if not match:
            continue
        yield match.group(1), unquote_dotenv_value(match.group(2)), line_number


def remove_dotenv_keys_text(text: str, keys: Collection[str]) -> tuple[str, bool]:
    key_set = set(keys)
    if not key_set:
        return text, False
    changed = False
    updated_lines: list[str] = []
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.strip()
        if line and not line.startswith("#"):
            match = _ENV_LINE.match(line)
            if match and match.group(1) in key_set:
                changed = True
                continue
        updated_lines.append(raw_line)
    return "".join(updated_lines), changed


def upsert_dotenv_key_text(text: str, key: str, value: str) -> str:
    lines = text.splitlines(keepends=True)
    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _ENV_LINE.match(line)
        if not match or match.group(1) != key:
            continue
        newline = "\n" if raw_line.endswith("\n") else ""
        lines[index] = f"{key}={value}{newline}"
        return "".join(lines)
    if text and not text.endswith("\n"):
        text += "\n"
    return f"{text}{key}={value}\n"
