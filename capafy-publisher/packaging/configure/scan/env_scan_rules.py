from __future__ import annotations
from typing import Optional

from pathlib import Path

from packaging.configure.sensitive.keywords import (
    contains_explicit_secret_keyword,
    contains_explicit_value_keyword,
    key_tokens,
    normalize_key_name,
)
from packaging.configure.sensitive.literals import (
    extract_assignment_value,
    infer_managed_value_type,
    looks_like_placeholder_value,
    looks_like_platform_managed_placeholder_value,
    looks_like_url_or_dsn,
)



ENDPOINT_CONFIG_KEYS = {
    "baseurl", "baseURL", "base_url",
    "url", "endpoint", "api_base",
}
_NORMALIZED_ENDPOINT_CONFIG_KEYS = {normalize_key_name(key) for key in ENDPOINT_CONFIG_KEYS}
NORMALIZED_ENDPOINT_SUFFIX_KEYS = ("baseurl", "apibase", "endpoint")

def is_endpoint_config_key(key: str) -> bool:
    normalized = normalize_key_name(key)
    if normalized in _NORMALIZED_ENDPOINT_CONFIG_KEYS:
        return True
    tokens = set(key_tokens(key))
    if {"base", "url"} <= tokens or {"api", "base"} <= tokens or "endpoint" in tokens:
        return True
    return any(normalized.endswith(suffix) for suffix in NORMALIZED_ENDPOINT_SUFFIX_KEYS)


def config_literal_candidate_kind(key: str, value: str) -> Optional[tuple[str, Optional[str], str]]:
    normalized = normalize_key_name(key)
    if contains_explicit_secret_keyword(key):
        extracted = extract_assignment_value(key, value)
        entry_type = "api_key"
        value_type = None
    elif contains_explicit_value_keyword(key):
        extracted = extract_assignment_value(key, value)
        entry_type = "managed_value"
        value_type = infer_managed_value_type(key, extracted or value)
    elif looks_like_url_or_dsn(value) and (
        "url" in normalized or "uri" in normalized or "dsn" in normalized or "endpoint" in normalized
    ):
        extracted = value.strip()
        entry_type = "managed_value"
        value_type = infer_managed_value_type(key, extracted)
    else:
        return None

    if (
        not extracted
        or looks_like_placeholder_value(extracted)
        or looks_like_platform_managed_placeholder_value(extracted)
    ):
        return None
    return entry_type, value_type, extracted


def logical_env_source_path(path: Path, fallback: str) -> str:
    parts = list(path.parts)
    if "_scan_only" in parts:
        index = parts.index("_scan_only")
        return "/".join(parts[index:])
    for marker in (".codex", ".claude", ".config"):
        if marker not in parts:
            continue
        index = parts.index(marker)
        suffix = parts[index:]
        return "/".join(suffix)
    return fallback


def candidate_source(source_display_path: str, detail: str) -> dict[str, str]:
    normalized_detail = str(detail or "").strip()
    if not normalized_detail:
        return {"source": source_display_path}
    return {
        "source": source_display_path,
        "source_detail": normalized_detail,
    }


__all__ = [
    "candidate_source",
    "config_literal_candidate_kind",
    "is_endpoint_config_key",
    "logical_env_source_path",
    "NORMALIZED_ENDPOINT_SUFFIX_KEYS",
]
