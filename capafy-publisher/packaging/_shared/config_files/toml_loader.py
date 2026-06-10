from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Optional

try:
    import tomllib  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - Python 3.8-3.10
    from packaging._shared.common import minimal_toml as tomllib  # type: ignore[no-redef]


_TOML_SECTION_RE = re.compile(r"^\s*\[([^\[\]]+)\]\s*(?:#.*)?$")
_TOML_KEY_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*=")


def safe_toml_loads(text: str) -> dict:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        if normalized == text:
            raise
        return tomllib.loads(normalized)


def _split_toml_path(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in str(value or "").strip().split(".") if part.strip())


def _toml_section_parts(raw_section: str) -> tuple[str, ...]:
    return _split_toml_path(raw_section)


def _toml_key_path_from_assignment_key(
    current_section: tuple[str, ...],
    assignment_key: str,
) -> tuple[tuple[str, ...], str]:
    key_parts = _split_toml_path(assignment_key)
    if not key_parts:
        return (), ""
    if current_section or len(key_parts) == 1:
        return current_section, key_parts[-1]
    return key_parts[:-1], key_parts[-1]


def find_toml_assignment_path_containing_value(text: str, needle: str) -> tuple[tuple[str, ...], str]:
    target = str(needle or "").strip()
    if not target:
        return (), ""
    current_section: tuple[str, ...] = ()
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r\n")
        section_match = _TOML_SECTION_RE.match(line)
        if section_match:
            current_section = _toml_section_parts(section_match.group(1).strip())
            continue
        key_match = _TOML_KEY_RE.match(line)
        if not key_match:
            continue
        value_text = line.split("=", 1)[1] if "=" in line else ""
        if target not in value_text:
            continue
        return _toml_key_path_from_assignment_key(current_section, key_match.group(1).strip())
    return (), ""


def find_toml_value_span(
    text: str,
    *,
    section: str = "",
    field: str,
    expected_value: str,
) -> Optional[tuple[int, int]]:
    target_section = _split_toml_path(section)
    target_field = str(field or "").strip()
    target_value = str(expected_value or "").strip()
    if not target_field or not target_value:
        return None

    current_section: tuple[str, ...] = ()
    offset = 0
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        line_offset = offset
        offset += len(raw_line)
        section_match = _TOML_SECTION_RE.match(line)
        if section_match:
            current_section = _toml_section_parts(section_match.group(1).strip())
            continue
        key_match = _TOML_KEY_RE.match(line)
        if not key_match:
            continue
        assignment_section, assignment_field = _toml_key_path_from_assignment_key(
            current_section,
            key_match.group(1).strip(),
        )
        if assignment_section != target_section or assignment_field != target_field:
            continue
        value_start, value_end, value_text = _toml_assignment_value_span(line, key_match.end(1))
        if _strip_wrapping_quotes(value_text) != target_value:
            continue
        return line_offset + value_start, line_offset + value_end
    return None


def replace_toml_value_text(
    text: str,
    *,
    section: str = "",
    field: str,
    replacement: str,
) -> str:
    target_section = _split_toml_path(section)
    target_field = str(field or "").strip()
    if not target_field:
        return text

    current_section: tuple[str, ...] = ()
    lines = text.splitlines(keepends=True)
    for index, raw_line in enumerate(lines):
        line = raw_line.rstrip("\r\n")
        section_match = _TOML_SECTION_RE.match(line)
        if section_match:
            current_section = _toml_section_parts(section_match.group(1).strip())
            continue
        key_match = _TOML_KEY_RE.match(line)
        if not key_match:
            continue
        assignment_section, assignment_field = _toml_key_path_from_assignment_key(
            current_section,
            key_match.group(1).strip(),
        )
        if assignment_section != target_section or assignment_field != target_field:
            continue
        value_start, value_end, _value_text = _toml_assignment_value_span(line, key_match.end(1))
        quoted_replacement = json.dumps(replacement, ensure_ascii=False)
        lines[index] = f"{line[:value_start]}{quoted_replacement}{line[value_end:]}{_line_ending(raw_line)}"
        break
    return "".join(lines)


def upsert_toml_value_file(path: Path, *, section: str = "", field: str, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
    except OSError:
        text = ""
    updated = upsert_toml_value_text(text, section=section, field=field, value=value)
    if updated != text or not path.is_file():
        path.write_text(updated, encoding="utf-8")


def upsert_toml_value_text(text: str, *, section: str = "", field: str, value: object) -> str:
    target_section_text = str(section or "").strip()
    target_section = _split_toml_path(target_section_text)
    target_field = str(field or "").strip()
    if not target_field:
        return text

    quoted_value = json.dumps(value, ensure_ascii=False)
    target_line = f"{target_field} = {quoted_value}\n"
    lines = text.splitlines(keepends=True)
    if not target_section:
        for raw_line in lines:
            line = raw_line.rstrip("\r\n")
            if _TOML_SECTION_RE.match(line):
                break
            key_match = _TOML_KEY_RE.match(line)
            if key_match and key_match.group(1).strip() == target_field:
                return text
        if text and not text.endswith("\n"):
            text += "\n"
        return f"{text}{target_line}"

    current_section: tuple[str, ...] = ()
    section_start: Optional[int] = None
    section_end = len(lines)
    for index, raw_line in enumerate(lines):
        section_match = _TOML_SECTION_RE.match(raw_line.rstrip("\r\n"))
        if not section_match:
            continue
        current_section = _toml_section_parts(section_match.group(1).strip())
        if section_start is not None:
            section_end = index
            break
        if current_section == target_section:
            section_start = index

    if section_start is not None:
        for index in range(section_start + 1, section_end):
            key_match = _TOML_KEY_RE.match(lines[index].rstrip("\r\n"))
            if key_match and key_match.group(1).strip() == target_field:
                return text
        lines.insert(section_end, target_line)
        return "".join(lines)

    if lines and lines[-1].strip():
        lines.append("\n")
    section_header = target_section_text or ".".join(target_section)
    lines.append(f"[{section_header}]\n")
    lines.append(target_line)
    return "".join(lines)


def _toml_assignment_value_span(line: str, key_end: int) -> tuple[int, int, str]:
    equals_index = line.find("=", key_end)
    if equals_index < 0:
        return len(line), len(line), ""
    raw_value = line[equals_index + 1 :]
    value_start = equals_index + 1 + len(raw_value) - len(raw_value.lstrip())
    value_text = raw_value.strip()
    value_end = value_start + len(value_text)
    return value_start, value_end, value_text


def _strip_wrapping_quotes(value: str) -> str:
    normalized = value.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {'"', "'"}:
        return normalized[1:-1].strip()
    return normalized


def _line_ending(raw_line: str) -> str:
    if raw_line.endswith("\r\n"):
        return "\r\n"
    if raw_line.endswith("\n"):
        return "\n"
    if raw_line.endswith("\r"):
        return "\r"
    return ""


def remove_toml_key_text(text: str, section_parts: tuple[str, ...], field: str) -> tuple[str, bool]:
    field_name = str(field or "").strip()
    if not field_name:
        return text, False
    normalized_section = tuple(str(part or "").strip() for part in section_parts if str(part or "").strip())
    dotted_key = ".".join((*normalized_section, field_name)) if normalized_section else field_name

    updated_lines: list[str] = []
    current_section: tuple[str, ...] = ()
    changed = False
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        section_match = _TOML_SECTION_RE.match(line)
        if section_match:
            current_section = _toml_section_parts(section_match.group(1).strip())
            updated_lines.append(raw_line)
            continue

        key_match = _TOML_KEY_RE.match(line)
        assignment_key = key_match.group(1).strip() if key_match else ""
        if assignment_key and (
            (current_section == normalized_section and assignment_key == field_name)
            or (current_section == () and assignment_key == dotted_key)
        ):
            changed = True
            continue
        updated_lines.append(raw_line)
    return "".join(updated_lines), changed


def remove_toml_key_containing_value_text(text: str, needle: str) -> tuple[str, bool]:
    section_parts, field = find_toml_assignment_path_containing_value(text, needle)
    if not field:
        return text, False
    return remove_toml_key_text(text, section_parts, field)


__all__ = [
    "find_toml_assignment_path_containing_value",
    "find_toml_value_span",
    "remove_toml_key_containing_value_text",
    "remove_toml_key_text",
    "replace_toml_value_text",
    "safe_toml_loads",
    "tomllib",
    "upsert_toml_value_file",
    "upsert_toml_value_text",
]
