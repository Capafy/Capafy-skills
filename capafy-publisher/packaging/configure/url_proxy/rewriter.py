from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from packaging.configure.contracts import (
    PlanField,
    SourceKind,
    UrlProxyPair,
)


_ENV_KEY_PATTERN = re.compile(r"^(\s*(?:export\s+)?)([A-Za-z_][A-Za-z0-9_]*)(\s*=\s*)(.*)$")
_TOML_KEY_VALUE = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_-]*)(\s*=\s*)(.*)$")
_TOML_SECTION = re.compile(r"^\s*\[([^\]]+)\]\s*$")


def _strip_dotenv_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value.strip()


def apply_url_proxy_to_staging(
    staging_root: Path,
    pairs: list[UrlProxyPair],
    *,
    field_rewrite_hook: Any = None,
    finalize_hook: Any = None,
) -> None:
    for pair in pairs:
        for plan_field in (pair.key, pair.url):
            if field_rewrite_hook and field_rewrite_hook(staging_root, plan_field, pair):
                continue
            if plan_field.source_kind == SourceKind.FILE:
                _replace_in_file(staging_root, plan_field)
            elif plan_field.source_kind == SourceKind.SYNTHESIZED:
                _synthesize_in_file(staging_root, plan_field)

    if finalize_hook:
        finalize_hook(staging_root, pairs)


def _replace_in_file(staging_root: Path, plan_field: PlanField) -> None:
    if not plan_field.location or not plan_field.source_relpath:
        return
    file_path = staging_root / plan_field.source_relpath
    if not file_path.is_file():
        return

    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        return

    fmt = plan_field.location.fmt
    if fmt == "dotenv":
        updated = _replace_dotenv_value(text, plan_field)
    elif fmt == "json":
        updated = _replace_json_value(text, plan_field)
    elif fmt == "toml":
        updated = _replace_toml_value(text, plan_field)
    else:
        return

    if updated != text:
        file_path.write_text(updated, encoding="utf-8")


def _replace_dotenv_value(text: str, plan_field: PlanField) -> str:
    placeholder = plan_field.placeholder
    occurrence_index = plan_field.location.occurrence_index if plan_field.location else 0
    original_value = str(plan_field.original_value or "").strip()
    if not original_value:
        return text
    lines = text.splitlines(keepends=True)
    target_occurrence = occurrence_index if occurrence_index > 0 else 1
    seen = 0
    for idx, raw_line in enumerate(lines):
        match = _ENV_KEY_PATTERN.match(raw_line.rstrip("\r\n"))
        if not match:
            continue
        if _strip_dotenv_value(match.group(4)) != original_value:
            continue
        seen += 1
        if seen != target_occurrence:
            continue
        newline = "\n" if raw_line.endswith("\n") else ""
        lines[idx] = f"{match.group(1)}{match.group(2)}{match.group(3)}{placeholder}{newline}"
        break
    return "".join(lines)


def _replace_json_value(text: str, plan_field: PlanField) -> str:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text

    pointer = plan_field.location.json_pointer if plan_field.location else ""
    if not pointer:
        return text

    parts = [p for p in pointer.split("/") if p]
    node = payload
    for part in parts[:-1]:
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return text

    if isinstance(node, dict) and parts and parts[-1] in node:
        node[parts[-1]] = plan_field.placeholder
        return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    return text


def _replace_toml_value(text: str, plan_field: PlanField) -> str:
    if not plan_field.location:
        return text
    target_section = plan_field.location.toml_section
    target_key = plan_field.field

    lines = text.splitlines(keepends=True)
    current_section = ""
    for idx, raw_line in enumerate(lines):
        line = raw_line.rstrip("\r\n")
        section_match = _TOML_SECTION.match(line)
        if section_match:
            current_section = section_match.group(1).strip()
            continue
        if current_section != target_section:
            continue
        kv_match = _TOML_KEY_VALUE.match(line)
        if not kv_match or kv_match.group(2) != target_key:
            continue
        newline = "\n" if raw_line.endswith("\n") else ""
        quoted_placeholder = json.dumps(plan_field.placeholder, ensure_ascii=False)
        lines[idx] = f"{kv_match.group(1)}{target_key}{kv_match.group(3)}{quoted_placeholder}{newline}"
        break
    return "".join(lines)


def _synthesize_in_file(staging_root: Path, plan_field: PlanField) -> None:
    if not plan_field.source_relpath:
        return
    file_path = staging_root / plan_field.source_relpath
    if plan_field.location and plan_field.location.fmt == "toml":
        _synthesize_toml_field(file_path, plan_field)
    elif plan_field.location and plan_field.location.fmt == "json":
        _synthesize_json_field(file_path, plan_field)


def _synthesize_toml_field(file_path: Path, plan_field: PlanField) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        text = file_path.read_text(encoding="utf-8") if file_path.is_file() else ""
    except OSError:
        text = ""

    target_section = plan_field.location.toml_section if plan_field.location else ""
    target_key = plan_field.field
    quoted_value = json.dumps(plan_field.placeholder, ensure_ascii=False)
    target_line = f"{target_key} = {quoted_value}\n"

    if not target_section:
        if text and not text.endswith("\n"):
            text += "\n"
        text += target_line
        file_path.write_text(text, encoding="utf-8")
        return

    lines = text.splitlines(keepends=True)
    section_start: Optional[int] = None
    section_end = len(lines)

    for idx, raw_line in enumerate(lines):
        section_match = _TOML_SECTION.match(raw_line.rstrip("\r\n"))
        if not section_match:
            continue
        if section_start is not None:
            section_end = idx
            break
        if section_match.group(1).strip() == target_section:
            section_start = idx

    if section_start is not None:
        for idx in range(section_start + 1, section_end):
            kv_match = _TOML_KEY_VALUE.match(lines[idx].rstrip("\r\n"))
            if kv_match and kv_match.group(2) == target_key:
                return
        lines.insert(section_end, target_line)
    else:
        if lines and lines[-1].strip():
            lines.append("\n")
        section_header_name = target_section
        lines.append(f"[{section_header_name}]\n")
        lines.append(target_line)

    file_path.write_text("".join(lines), encoding="utf-8")


def _synthesize_json_field(file_path: Path, plan_field: PlanField) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        text = file_path.read_text(encoding="utf-8") if file_path.is_file() else "{}"
        payload = json.loads(text)
    except (OSError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    pointer = plan_field.location.json_pointer if plan_field.location else ""
    if pointer:
        parts = [p for p in pointer.split("/") if p]
        node = payload
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node[part] = {}
            node = node[part]
        if parts:
            node[parts[-1]] = plan_field.placeholder
    else:
        payload[plan_field.field] = plan_field.placeholder

    file_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


__all__ = ["apply_url_proxy_to_staging"]
