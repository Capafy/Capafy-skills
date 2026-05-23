from __future__ import annotations

from pathlib import Path
from typing import Any

from packaging._shared.common.constants import OPENAI_OFFICIAL_URL_V1
from packaging._shared.common.toml_loader import safe_toml_loads, tomllib
from packaging.configure.runtimes.toml_text import (
    KEY_VALUE_PATTERN as _TOML_ASSIGNMENT_PATTERN,
    SECTION_PATTERN as _CODEX_PROVIDER_SECTION_PATTERN,
    newline_for as _newline_for,
    toml_string as _toml_string,
)
from packaging.configure.sensitive.keywords import normalize_key_name
from packaging._shared.reviewed_scan.query import reviewed_url_proxy_groups as _reviewed_url_proxy_groups


_ENDPOINT_SUFFIX_KEYS = ("baseurl", "apibase", "endpoint")


def official_codex_url_for_env_key(env_key: str) -> str:
    return OPENAI_OFFICIAL_URL_V1 if str(env_key or "").strip() else ""


def _looks_like_openai_model(model_name: str) -> bool:
    normalized = str(model_name or "").strip().lower()
    if not normalized:
        return False
    if normalized.startswith("openai/"):
        normalized = normalized.split("/", 1)[1]
    if normalized.startswith(("gpt", "o1", "o3", "o4")):
        return True
    if normalized in {"codex-mini-latest", "codex-latest"}:
        return True
    if normalized.startswith("codex-"):
        return True
    return False


def _provider_base_url(provider_payload: dict) -> str:
    for raw_key, raw_value in provider_payload.items():
        if not isinstance(raw_value, str) or not raw_value.strip():
            continue
        normalized_key = normalize_key_name(str(raw_key))
        if normalized_key == "url":
            return raw_value.strip()
        if any(normalized_key.endswith(suffix) for suffix in _ENDPOINT_SUFFIX_KEYS):
            return raw_value.strip()
    return ""


def infer_selected_codex_provider_url(
    env_key: str,
    *,
    top_level_model: str = "",
) -> str:
    official_url = official_codex_url_for_env_key(env_key)
    if official_url:
        return official_url
    if _looks_like_openai_model(top_level_model):
        return OPENAI_OFFICIAL_URL_V1
    return ""


def collect_codex_official_base_url_targets(config_text: str) -> list[dict[str, str]]:
    try:
        payload = safe_toml_loads(config_text)
    except tomllib.TOMLDecodeError:
        return []
    if not isinstance(payload, dict):
        return []

    providers = payload.get("model_providers")
    if not isinstance(providers, dict):
        return []

    top_level_model = str(payload.get("model", "")).strip()

    inferred_targets: list[dict[str, str]] = []
    for provider_name, provider_payload in providers.items():
        if not isinstance(provider_payload, dict):
            continue
        env_key = str(provider_payload.get("env_key", "")).strip()
        if not env_key or _provider_base_url(provider_payload):
            continue
        official_url = official_codex_url_for_env_key(env_key)
        if not official_url:
            continue
        inferred_targets.append(
            {
                "provider_name": str(provider_name).strip(),
                "env_key": env_key,
                "url": infer_selected_codex_provider_url(env_key, top_level_model=top_level_model),
            }
        )
    return inferred_targets


def _allowed_provider_names(reviewed_scan: dict[str, Any]) -> set[str]:
    prefix = ".codex/config.toml#model_providers."
    providers: set[str] = set()
    for group in _reviewed_url_proxy_groups(reviewed_scan):
        if not group.startswith(prefix):
            continue
        provider = group[len(prefix) :].split(".", 1)[0].strip()
        if provider:
            providers.add(provider.strip("\"'"))
    return providers


def _confirmed_model_by_provider(reviewed_scan: dict[str, Any]) -> dict[str, str]:
    prefix = ".codex/config.toml#model_providers."
    models: dict[str, str] = {}
    url_proxy = reviewed_scan.get("url_proxy", [])
    if not isinstance(url_proxy, list):
        return models
    for entry in url_proxy:
        if not isinstance(entry, dict):
            continue
        group = str(entry.get("url_proxy_group", "") or "").strip()
        if not group.startswith(prefix):
            continue
        provider = group[len(prefix) :].split(".", 1)[0].strip().strip("\"'")
        model = str(entry.get("model", "") or "").strip()
        if provider and model:
            models[provider] = model
    return models


def _toml_provider_name(section_name: str) -> str | None:
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
    allowed = _allowed_provider_names(reviewed_scan)
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
    confirmed_models = _confirmed_model_by_provider(reviewed_scan)
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
    "infer_selected_codex_provider_url",
    "official_codex_url_for_env_key",
    "rewrite_codex_confirmed_providers",
]
