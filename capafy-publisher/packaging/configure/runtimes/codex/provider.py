from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from packaging._shared.common.constants import OPENAI_OFFICIAL_URL_V1
from packaging._shared.common.toml_loader import safe_toml_loads, tomllib
from packaging.configure.runtimes.toml_text import (
    KEY_VALUE_PATTERN as _TOML_ASSIGNMENT_PATTERN,
    SECTION_PATTERN as _CODEX_PROVIDER_SECTION_PATTERN,
    newline_for as _newline_for,
    toml_string as _toml_string,
)
from packaging.configure.runtimes.codex.auth import CODEX_AUTH_PROVIDER_NAME
from packaging.configure.runtimes.codex.config_state import load_codex_config_state_from_text


_CODEX_PROVIDER_GROUP_PREFIX = ".codex/config.toml#model_providers."


def collect_codex_official_base_url_targets(config_text: str) -> list[dict[str, str]]:
    state = load_codex_config_state_from_text(config_text).provider
    if state is None:
        return []
    if not state.provider_exists or state.base_url or state.selected_provider != CODEX_AUTH_PROVIDER_NAME:
        return []
    if not state.env_key:
        return []
    return [{
        "provider_name": state.selected_provider,
        "env_key": state.env_key,
        "url": OPENAI_OFFICIAL_URL_V1,
    }]


def _provider_name_from_group(group: object) -> str:
    normalized = str(group or "").strip()
    if not normalized.startswith(_CODEX_PROVIDER_GROUP_PREFIX):
        return ""
    return normalized[len(_CODEX_PROVIDER_GROUP_PREFIX) :].split(".", 1)[0].strip().strip("\"'")


def _confirmed_provider_summary(reviewed_scan: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {"providers": set(), "models": {}}
    url_proxy = reviewed_scan.get("url_proxy", [])
    if not isinstance(url_proxy, list):
        return summary
    for entry in url_proxy:
        if not isinstance(entry, dict):
            continue
        provider = _provider_name_from_group(entry.get("url_proxy_group", ""))
        if not provider:
            continue
        summary["providers"].add(provider)
        model = str(entry.get("model", "") or "").strip()
        if model:
            summary["models"][provider] = model
    return summary


def _toml_provider_name(section_name: str) -> Optional[str]:
    normalized = str(section_name or "").strip()
    if not normalized.startswith("model_providers."):
        return None
    suffix = normalized[len("model_providers.") :].strip()
    if len(suffix) >= 2 and suffix[0] == suffix[-1] and suffix[0] in {"'", '"'}:
        return suffix[1:-1]
    return suffix or None


def _load_toml_payload(text: str) -> dict[str, Any]:
    try:
        payload = safe_toml_loads(text)
    except tomllib.TOMLDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _provider_order(payload: dict[str, Any]) -> list[str]:
    providers = payload.get("model_providers")
    if not isinstance(providers, dict):
        return []
    return [str(name).strip() for name in providers if str(name).strip()]


def _rewrite_model_provider_lines(
    text: str,
    *,
    selected_provider: str,
    allowed_providers: set[str],
) -> tuple[str, int]:
    newline = _newline_for(text)
    lines = text.splitlines(keepends=True)
    changed = 0
    current_section = ""
    first_section_index = len(lines)
    top_level_model_provider_seen = False

    def replacement_line(indent: str, key: str, separator: str, suffix: str) -> str:
        return f"{indent}{key}{separator}{_toml_string(selected_provider)}{suffix}{newline}"

    for index, raw_line in enumerate(lines):
        line = raw_line.rstrip("\r\n")
        section_match = _CODEX_PROVIDER_SECTION_PATTERN.match(line)
        if section_match:
            current_section = section_match.group(1).strip()
            first_section_index = min(first_section_index, index)
            continue
        match = _TOML_ASSIGNMENT_PATTERN.match(line)
        if not match or match.group(2) != "model_provider":
            continue
        old_value = match.group(4).strip().strip("\"'")
        in_profile = current_section.startswith("profiles.")
        if current_section and not in_profile:
            continue
        if not current_section:
            top_level_model_provider_seen = True
        if old_value in allowed_providers:
            continue
        updated = replacement_line(match.group(1), match.group(2), match.group(3), match.group(5))
        if raw_line != updated:
            lines[index] = updated
            changed += 1

    if not top_level_model_provider_seen:
        insert_index = first_section_index
        if insert_index > 0 and lines and lines[insert_index - 1].strip():
            lines.insert(insert_index, newline)
            insert_index += 1
        lines.insert(insert_index, f"model_provider = {_toml_string(selected_provider)}{newline}")
        changed += 1
    return "".join(lines), changed


def _rewrite_top_level_model_line(text: str, *, model: str) -> tuple[str, int]:
    if not model:
        return text, 0
    newline = _newline_for(text)
    lines = text.splitlines(keepends=True)
    changed = 0
    current_section = ""
    first_section_index = len(lines)
    top_level_model_seen = False

    for index, raw_line in enumerate(lines):
        line = raw_line.rstrip("\r\n")
        section_match = _CODEX_PROVIDER_SECTION_PATTERN.match(line)
        if section_match:
            current_section = section_match.group(1).strip()
            first_section_index = min(first_section_index, index)
            continue
        match = _TOML_ASSIGNMENT_PATTERN.match(line)
        if not match or match.group(2) != "model" or current_section:
            continue
        top_level_model_seen = True
        old_value = match.group(4).strip().strip("\"'")
        if old_value == model:
            continue
        updated = f"{match.group(1)}{match.group(2)}{match.group(3)}{_toml_string(model)}{match.group(5)}{newline}"
        if raw_line != updated:
            lines[index] = updated
            changed += 1

    if not top_level_model_seen:
        insert_index = first_section_index
        if insert_index > 0 and lines and lines[insert_index - 1].strip():
            lines.insert(insert_index, newline)
            insert_index += 1
        lines.insert(insert_index, f"model = {_toml_string(model)}{newline}")
        changed += 1
    return "".join(lines), changed


def _remove_unconfirmed_provider_sections(
    text: str,
    *,
    allowed_providers: set[str],
) -> tuple[str, int]:
    lines = text.splitlines(keepends=True)
    updated_lines: list[str] = []
    removed = 0
    skip_section = False

    for raw_line in lines:
        section_match = _CODEX_PROVIDER_SECTION_PATTERN.match(raw_line.rstrip("\r\n"))
        if section_match:
            provider = _toml_provider_name(section_match.group(1).strip())
            skip_section = bool(provider and provider not in allowed_providers)
            if skip_section:
                removed += 1
                continue
        if skip_section:
            continue
        updated_lines.append(raw_line)
    return "".join(updated_lines), removed


def rewrite_codex_confirmed_providers(
    staging_root: Path,
    reviewed_scan: dict[str, Any],
) -> dict[str, Any]:
    confirmed_summary = _confirmed_provider_summary(reviewed_scan)
    allowed = confirmed_summary["providers"]
    if not allowed:
        return {"codex_confirmed_provider_rewrites": 0}
    config_path = staging_root / ".codex" / "config.toml"
    if not config_path.is_file():
        return {"codex_confirmed_provider_rewrites": 0}

    original_text = config_path.read_text(encoding="utf-8")
    payload = _load_toml_payload(original_text)
    ordered_allowed = [provider for provider in _provider_order(payload) if provider in allowed]
    if not ordered_allowed:
        return {"codex_confirmed_provider_rewrites": 0}
    selected_provider = ordered_allowed[0]

    updated_text, removed = _remove_unconfirmed_provider_sections(
        original_text,
        allowed_providers=set(ordered_allowed),
    )
    updated_text, model_provider_rewrites = _rewrite_model_provider_lines(
        updated_text,
        selected_provider=selected_provider,
        allowed_providers=set(ordered_allowed),
    )
    confirmed_models = confirmed_summary["models"]
    updated_text, model_rewrites = _rewrite_top_level_model_line(
        updated_text,
        model=confirmed_models.get(selected_provider, ""),
    )
    if updated_text != original_text:
        config_path.write_text(updated_text, encoding="utf-8")
    return {
        "codex_confirmed_provider_rewrites": removed + model_provider_rewrites + model_rewrites,
        "codex_confirmed_provider_selected": selected_provider if updated_text != original_text else "",
        "codex_confirmed_provider_removed": removed,
        "codex_confirmed_model_rewrites": model_rewrites,
    }




__all__ = [
    "collect_codex_official_base_url_targets",
    "rewrite_codex_confirmed_providers",
]
