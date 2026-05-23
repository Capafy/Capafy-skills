from __future__ import annotations

import re
from pathlib import Path

from packaging.configure.runtimes.toml_text import toml_string as _toml_string


_TOML_KEY_VALUE = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_-]*)(\s*=\s*)(.*)$")
_TOML_SECTION = re.compile(r"^\s*\[([^\]]+)\]\s*$")


def provider_name_from_codex_section(section: str) -> str:
    normalized = str(section or "").strip()
    prefix = "model_providers."
    if not normalized.startswith(prefix):
        return ""
    provider = normalized[len(prefix) :].strip()
    if len(provider) >= 2 and provider[0] == provider[-1] and provider[0] in {"'", '"'}:
        provider = provider[1:-1]
    return provider or ""


def provider_name_from_pair_group(group: str) -> str:
    normalized = str(group or "").strip()
    marker = "#model_providers."
    if marker not in normalized:
        return ""
    provider = normalized.rsplit(marker, 1)[1].split("#", 1)[0].strip()
    if len(provider) >= 2 and provider[0] == provider[-1] and provider[0] in {"'", '"'}:
        provider = provider[1:-1]
    return provider or ""


def ensure_provider_section(
    config_path: Path,
    *,
    provider: str,
    env_key: str,
    base_url_placeholder: str,
    synthesize_group: bool,
) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        text = config_path.read_text(encoding="utf-8") if config_path.is_file() else ""
    except OSError:
        text = ""

    lines = text.splitlines(keepends=True)
    section_name = f"model_providers.{provider}"
    section_start: int | None = None
    section_end = len(lines)
    top_level_provider_seen = False
    provider_section_count = 0
    current_section = ""

    for idx, raw_line in enumerate(lines):
        line = raw_line.rstrip("\r\n")
        section_match = _TOML_SECTION.match(line)
        if section_match:
            current_section = section_match.group(1).strip()
            if provider_name_from_codex_section(current_section):
                provider_section_count += 1
            if section_start is not None:
                section_end = idx
                break
            if current_section == section_name:
                section_start = idx
            continue
        kv_match = _TOML_KEY_VALUE.match(line)
        if kv_match and not current_section and kv_match.group(2) == "model_provider":
            top_level_provider_seen = True

    if section_start is None:
        if lines and lines[-1].strip():
            lines.append("\n")
        section_start = len(lines)
        lines.append(f"[{section_name}]\n")
        section_end = len(lines)
        provider_section_count += 1

    section_keys = _keys_in_section(lines, section_start, section_end)
    insert_at = section_end
    if "name" not in section_keys:
        lines.insert(insert_at, f"name = {_toml_string(provider)}\n")
        insert_at += 1
        section_end += 1
    if "env_key" not in section_keys:
        lines.insert(insert_at, f"env_key = {_toml_string(env_key)}\n")
        insert_at += 1
        section_end += 1
    if "base_url" not in section_keys:
        lines.insert(insert_at, f"base_url = {_toml_string(base_url_placeholder)}\n")
        insert_at += 1
        section_end += 1
    if "wire_api" not in section_keys:
        lines.insert(insert_at, 'wire_api = "responses"\n')
        insert_at += 1
        section_end += 1
    if "requires_openai_auth" not in section_keys:
        lines.insert(insert_at, "requires_openai_auth = false\n")

    if synthesize_group and not top_level_provider_seen and provider_section_count == 1:
        insert_at = _first_section_index(lines)
        if insert_at > 0 and lines[insert_at - 1].strip():
            lines.insert(insert_at, "\n")
            insert_at += 1
        lines.insert(insert_at, f"model_provider = {_toml_string(provider)}\n")

    updated = "".join(lines)
    if updated != text:
        config_path.write_text(updated, encoding="utf-8")


def remove_top_level_toml_key(config_path: Path, key: str) -> None:
    try:
        text = config_path.read_text(encoding="utf-8") if config_path.is_file() else ""
    except OSError:
        return
    lines = text.splitlines(keepends=True)
    updated_lines: list[str] = []
    current_section = ""
    removed = False
    for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        section_match = _TOML_SECTION.match(line)
        if section_match:
            current_section = section_match.group(1).strip()
            updated_lines.append(raw_line)
            continue
        kv_match = _TOML_KEY_VALUE.match(line)
        if not current_section and kv_match and kv_match.group(2) == key:
            removed = True
            continue
        updated_lines.append(raw_line)
    if removed:
        config_path.write_text("".join(updated_lines), encoding="utf-8")


def disable_requires_openai_auth(staging_root: Path) -> None:
    config_path = staging_root / ".codex" / "config.toml"
    if not config_path.is_file():
        return
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError:
        return

    lines = text.splitlines(keepends=True)
    changed = False
    for idx, raw_line in enumerate(lines):
        kv_match = _TOML_KEY_VALUE.match(raw_line.rstrip("\r\n"))
        if not kv_match or kv_match.group(2) != "requires_openai_auth":
            continue
        raw_value = kv_match.group(4).strip().strip("\"'").lower()
        if raw_value in {"1", "true", "yes"}:
            newline = "\n" if raw_line.endswith("\n") else ""
            lines[idx] = f"{kv_match.group(1)}requires_openai_auth{kv_match.group(3)}false{newline}"
            changed = True

    if changed:
        config_path.write_text("".join(lines), encoding="utf-8")


def _keys_in_section(lines: list[str], section_start: int, section_end: int) -> set[str]:
    keys: set[str] = set()
    for idx in range(section_start + 1, section_end):
        match = _TOML_KEY_VALUE.match(lines[idx].rstrip("\r\n"))
        if match:
            keys.add(match.group(2))
    return keys


def _first_section_index(lines: list[str]) -> int:
    for idx, raw_line in enumerate(lines):
        if _TOML_SECTION.match(raw_line.rstrip("\r\n")):
            return idx
    return len(lines)


__all__ = [
    "disable_requires_openai_auth",
    "ensure_provider_section",
    "provider_name_from_codex_section",
    "provider_name_from_pair_group",
    "remove_top_level_toml_key",
]
