from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from packaging._shared.common.url_values import build_config_url_proxy_group
from packaging.configure.scan.env_scan_rules import (
    candidate_source,
    config_literal_candidate_kind,
    is_endpoint_config_key,
)
from packaging.configure.scan.support import append_candidate as _append_candidate
from packaging.configure.runtimes.codex.auth import should_skip_codex_auth_structured_scan
from packaging.configure.runtimes.codex.provider import collect_codex_official_base_url_targets
from packaging.configure.sensitive.keywords import normalize_key_name
from packaging.configure.sensitive.literals import looks_like_url_or_dsn


def is_codex_model_provider_section(section: str) -> bool:
    normalized = str(section or "").strip()
    return normalized.startswith("model_providers.") and bool(normalized[len("model_providers.") :].strip())


def should_scan_codex_structured_values(relpath: str) -> bool:
    if should_skip_codex_auth_structured_scan(relpath):
        return False
    return Path(str(relpath or "")).name != "config.toml"


def _attach_url_proxy_env_name(candidates: list[dict], group: str, env_name: str) -> None:
    normalized_env_name = str(env_name or "").strip()
    if not group or not normalized_env_name:
        return
    for candidate in candidates:
        if str(candidate.get("url_proxy_group", "") or "").strip() != group:
            continue
        if candidate.get("value_type") != "url":
            continue
        env_names = candidate.setdefault("url_proxy_env_names", [])
        if isinstance(env_names, list) and normalized_env_name not in env_names:
            env_names.append(normalized_env_name)


def collect_codex_toml_config_hints(
    text: str,
    display_path: str,
    source_display_path: str,
    annotate_candidate: Callable[[dict, str], dict | None],
) -> tuple[dict[str, str], dict[str, str], list[dict]]:
    env_url_hints: dict[str, str] = {}
    value_url_hints: dict[str, str] = {}
    candidates: list[dict] = []
    section_env_keys: dict[str, str] = {}
    section_base_urls: dict[str, str] = {}

    kv_pattern = re.compile(r'^\s*(\w[\w.-]*)\s*=\s*"([^"]+)"\s*$')
    current_section = ""

    for line_no, line in enumerate(text.splitlines(), start=1):
        section_match = re.match(r'^\s*\[([^\]]+)\]', line)
        if section_match:
            current_section = section_match.group(1)
            continue

        kv_match = kv_pattern.match(line)
        if not kv_match:
            continue

        key = kv_match.group(1)
        value = kv_match.group(2)
        service = current_section.split(".")[-1] if current_section else "unknown"
        is_codex_provider_section = is_codex_model_provider_section(current_section)

        if is_endpoint_config_key(key):
            if value.startswith("http://") or value.startswith("https://"):
                env_url_hints[f"{current_section}.{key}"] = value
                value_url_hints[value] = value
                if is_codex_provider_section:
                    section_base_urls[current_section] = value
                env_key = section_env_keys.get(current_section, "").strip()
                url_proxy_group = (
                    build_config_url_proxy_group(source_display_path, current_section)
                    if is_codex_provider_section
                    else ""
                )
                if env_key and is_codex_provider_section:
                    env_url_hints[env_key] = value
                source_detail = f"line {line_no} [{current_section}]"
                candidate_payload = {
                    "entry_type": "managed_value",
                    "field": key,
                    "value_type": "url",
                    "value": value,
                    "service": service,
                    "default_url": value,
                    "local_url": value,
                    "source": source_display_path,
                    "source_detail": source_detail,
                    "env_name": None,
                }
                if url_proxy_group:
                    candidate_payload["url_proxy_group"] = url_proxy_group
                    candidate_payload["url_proxy_env_names"] = [env_key] if env_key else []
                _append_candidate(
                    candidates,
                    annotate_candidate(candidate_payload, display_path)
                )
            continue

        if normalize_key_name(key) == "envkey":
            if is_codex_provider_section:
                section_env_keys[current_section] = value
                base_url = section_base_urls.get(current_section, "").strip()
                if base_url:
                    env_url_hints[value] = base_url
                _attach_url_proxy_env_name(
                    candidates,
                    build_config_url_proxy_group(source_display_path, current_section),
                    value,
                )
            continue

        candidate_kind = config_literal_candidate_kind(key, value)
        if candidate_kind is None:
            continue
        entry_type, value_type, extracted = candidate_kind
        managed_url = extracted.strip() if looks_like_url_or_dsn(extracted) else "unknown"

        candidate_payload = {
            "entry_type": entry_type,
            "field": key,
            "value_type": value_type,
            "value": extracted,
            "service": service,
            "default_url": managed_url,
            "local_url": managed_url,
            "source": source_display_path,
            "source_detail": f"line {line_no} [{current_section}]",
            "env_name": None,
        }
        if is_codex_provider_section and entry_type == "api_key":
            candidate_payload["url_proxy_group"] = build_config_url_proxy_group(source_display_path, current_section)
        candidate = annotate_candidate(candidate_payload, display_path)
        _append_candidate(candidates, candidate)

    for item in collect_codex_official_base_url_targets(text):
        env_key = str(item.get("env_key", "")).strip()
        url = str(item.get("url", "")).strip()
        provider_name = str(item.get("provider_name", "")).strip()
        if env_key and url:
            env_url_hints.setdefault(env_key, url)
            value_url_hints.setdefault(url, url)
            _append_candidate(
                candidates,
                annotate_candidate(
                    {
                        "entry_type": "managed_value",
                        "field": "base_url",
                        "value_type": "url",
                        "value": url,
                        "service": provider_name or "unknown",
                        "default_url": url,
                        "local_url": url,
                        "source": source_display_path,
                        "source_detail": f"model_providers.{provider_name}.base_url" if provider_name else "",
                        "env_name": None,
                    },
                    display_path,
                )
            )

    return env_url_hints, value_url_hints, candidates


__all__ = [
    "collect_codex_toml_config_hints",
    "is_codex_model_provider_section",
    "should_scan_codex_structured_values",
]
