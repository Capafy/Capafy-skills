from __future__ import annotations

from typing import Any

from packaging.configure.sensitive.keywords import (
    contains_explicit_secret_keyword,
    contains_explicit_value_keyword,
)
from packaging.configure.sensitive.literals import (
    extract_assignment_value,
    extract_secret_value,
    infer_managed_value_type,
    looks_like_secret_literal,
    looks_like_placeholder_value,
    looks_like_url_or_dsn,
)


CONFIG_REL = ".hermes/config.yaml"
_PROVIDER_ROOT_KEYS = frozenset({
    "model",
    "auxiliary",
    "delegation",
    "providers",
    "fallback_providers",
    "custom_providers",
})
_HERMES_SECRET_FIELDS = frozenset({
    "gateway.relay_secret",
    "gateway.relay_delivery_key",
})
_PROVIDER_HEADER_MAP_KEYS = frozenset({"default_headers", "extra_headers"})


def collect_hermes_config_hints(
    payload: dict[str, Any],
    annotate_candidate,
) -> tuple[dict[str, str], dict[str, str], dict[str, str], list[dict]]:
    candidates: list[dict] = []
    for path_parts, key, value in _iter_non_provider_string_leaves(payload):
        field = ".".join(path_parts)
        extracted_value = _extract_hermes_config_value(field, key, value)
        if not extracted_value:
            continue
        entry_type = "api_key" if _is_hermes_secret_field(field, key) else "managed_value"
        value_type = None if entry_type == "api_key" else infer_managed_value_type(key, extracted_value)
        metadata_url = extracted_value.strip() if looks_like_url_or_dsn(extracted_value) else "unknown"
        candidate = annotate_candidate(
            {
                "entry_type": entry_type,
                "field": field,
                "value_type": value_type,
                "value": extracted_value,
                "service": _service_from_path(path_parts, key),
                "default_url": metadata_url,
                "local_url": metadata_url,
                "source": CONFIG_REL,
                "source_detail": "yaml:" + field,
                "env_name": None,
            },
            CONFIG_REL,
        )
        if candidate is not None:
            candidates.append(candidate)
    for path_parts, key, value in _iter_provider_header_string_leaves(payload):
        field = ".".join(path_parts)
        extracted_value = _extract_hermes_header_value(key, value)
        if not extracted_value:
            continue
        entry_type = "api_key" if contains_explicit_secret_keyword(key) else "managed_value"
        value_type = None if entry_type == "api_key" else infer_managed_value_type(key, extracted_value)
        metadata_url = extracted_value.strip() if looks_like_url_or_dsn(extracted_value) else "unknown"
        candidate = annotate_candidate(
            {
                "entry_type": entry_type,
                "field": field,
                "value_type": value_type,
                "value": extracted_value,
                "service": _service_from_path(path_parts, key),
                "default_url": metadata_url,
                "local_url": metadata_url,
                "source": CONFIG_REL,
                "source_detail": "yaml:" + field,
                "env_name": None,
            },
            CONFIG_REL,
        )
        if candidate is not None:
            candidates.append(candidate)
    return {}, {}, {}, candidates


def _extract_hermes_config_value(field: str, key: str, value: str) -> str:
    if _is_hermes_secret_field(field, key):
        secret_value = extract_secret_value(key, value)
        return secret_value if secret_value and looks_like_secret_literal(secret_value) else ""
    return extract_assignment_value(key, value) or ""


def _extract_hermes_header_value(key: str, value: str) -> str:
    if contains_explicit_secret_keyword(key):
        secret_value = extract_secret_value(key, value)
        return secret_value if secret_value and looks_like_secret_literal(secret_value) else ""
    if not contains_explicit_value_keyword(key):
        return ""
    extracted = extract_assignment_value(key, value)
    if extracted:
        return extracted
    stripped = value.strip()
    if not stripped or looks_like_placeholder_value(stripped):
        return ""
    if stripped.isupper() and all(char.isalnum() or char == "_" for char in stripped):
        return ""
    return stripped


def _is_hermes_secret_field(field: str, key: str) -> bool:
    return field in _HERMES_SECRET_FIELDS or contains_explicit_secret_keyword(key)


def _iter_non_provider_string_leaves(payload: dict[str, Any]) -> list[tuple[list[str], str, str]]:
    result: list[tuple[list[str], str, str]] = []
    for key, value in payload.items():
        key_text = str(key)
        if key_text in _PROVIDER_ROOT_KEYS:
            continue
        _append_string_leaves(value, [key_text], result)
    return result


def _append_string_leaves(node: object, path_parts: list[str], result: list[tuple[list[str], str, str]]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            key_text = str(key)
            _append_string_leaves(value, [*path_parts, key_text], result)
        return
    if isinstance(node, list):
        for index, value in enumerate(node):
            _append_string_leaves(value, [*path_parts, str(index)], result)
        return
    if isinstance(node, str) and path_parts:
        result.append((path_parts, path_parts[-1], node))


def _iter_provider_header_string_leaves(payload: dict[str, Any]) -> list[tuple[list[str], str, str]]:
    result: list[tuple[list[str], str, str]] = []
    for key, value in payload.items():
        key_text = str(key)
        if key_text not in _PROVIDER_ROOT_KEYS:
            continue
        _append_provider_header_string_leaves(value, [key_text], result)
    return result


def _append_provider_header_string_leaves(
    node: object,
    path_parts: list[str],
    result: list[tuple[list[str], str, str]],
) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            key_text = str(key)
            next_path = [*path_parts, key_text]
            if key_text in _PROVIDER_HEADER_MAP_KEYS and isinstance(value, dict):
                _append_header_map_string_leaves(value, next_path, result)
                continue
            _append_provider_header_string_leaves(value, next_path, result)
        return
    if isinstance(node, list):
        for index, value in enumerate(node):
            _append_provider_header_string_leaves(value, [*path_parts, str(index)], result)


def _append_header_map_string_leaves(
    node: dict,
    path_parts: list[str],
    result: list[tuple[list[str], str, str]],
) -> None:
    for key, value in node.items():
        key_text = str(key)
        if isinstance(value, str):
            result.append(([*path_parts, key_text], key_text, value))


def _service_from_path(path_parts: list[str], key: str) -> str:
    for part in path_parts[:-1]:
        normalized = str(part or "").strip()
        if normalized and not normalized.isdigit():
            return normalized
    return key


def should_scan_hermes_structured_values(relpath: str) -> bool:
    normalized = str(relpath or "").strip().replace("\\", "/")
    return normalized not in {
        ".hermes/config.yaml",
        "_scan_only/.hermes/config.yaml",
    }


__all__ = [
    "collect_hermes_config_hints",
    "should_scan_hermes_structured_values",
]
