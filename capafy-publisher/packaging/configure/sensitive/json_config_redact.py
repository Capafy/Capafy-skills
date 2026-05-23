from __future__ import annotations

import json
from pathlib import Path

from packaging._shared.common.json_walk import walk_json_strings
from packaging._shared.common.local_path_detection import LOCAL_PATH_PLACEHOLDER, looks_like_local_path
from packaging._shared.policies.path_refs import is_packaged_runtime_ref
from packaging.configure.sensitive.keywords import (
    contains_explicit_secret_keyword,
    contains_explicit_value_keyword,
    normalize_key_name,
)
from packaging.configure.sensitive.literals import (
    extract_assignment_value,
    extract_secret_value,
    infer_managed_value_type,
    looks_like_platform_managed_placeholder_value,
    looks_like_secret_literal,
)
from packaging.configure.sensitive.placeholders import build_redaction_placeholder


_RUNTIME_LLM_CONFIG_KEYS = {
    "apikey",
    "apikeys",
    "apiurl",
    "baseurl",
    "envkey",
    "openaikey",
    "openaiapikey",
    "openaibaseurl",
    "anthropicapikey",
    "anthropicauthtoken",
    "anthropicbaseurl",
    "authorization",
}







_DEV_ONLY_TOP_LEVEL_JSON_KEYS = ("hooks",)


def _is_runtime_llm_config_key(key: str) -> bool:
    return normalize_key_name(key) in _RUNTIME_LLM_CONFIG_KEYS


def _strip_dev_only_top_level_json_keys(text: str) -> tuple[str, int]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text, 0
    if not isinstance(payload, dict):
        return text, 0
    removed = 0
    for key in _DEV_ONLY_TOP_LEVEL_JSON_KEYS:
        if key in payload:
            del payload[key]
            removed += 1
    if not removed:
        return text, 0
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n", removed


def _redact_json_local_payload(payload: object, *, source: str) -> tuple[object, int]:
    def redact_value(node: str, key_name: str | None) -> tuple[str, int]:
        if looks_like_platform_managed_placeholder_value(node):
            return node, 0
        if is_packaged_runtime_ref(node):
            return node, 0
        normalized_key = key_name or ""

        if contains_explicit_secret_keyword(normalized_key):
            extracted_value = extract_secret_value(normalized_key, node)
            if extracted_value and looks_like_secret_literal(extracted_value):
                return build_redaction_placeholder(
                    source,
                    field=normalized_key,
                    source_detail="",
                    value_type=infer_managed_value_type(normalized_key, extracted_value),
                ), 1

        if contains_explicit_value_keyword(normalized_key):
            extracted_value = extract_assignment_value(normalized_key, node)
            if extracted_value:
                return build_redaction_placeholder(
                    source,
                    field=normalized_key,
                    source_detail="",
                    value_type=infer_managed_value_type(normalized_key, extracted_value),
                ), 1

        if looks_like_local_path(node):
            return LOCAL_PATH_PLACEHOLDER, 1
        return node, 0

    return walk_json_strings(payload, redact_value)


def _redact_json_stage_payload(payload: object) -> tuple[object, int]:
    def redact_value(node: str, key_name: str | None) -> tuple[str, int]:
        if looks_like_platform_managed_placeholder_value(node):
            return node, 0
        if is_packaged_runtime_ref(node):
            return node, 0
        if _is_runtime_llm_config_key(key_name or ""):
            return node, 0
        if looks_like_local_path(node):
            return LOCAL_PATH_PLACEHOLDER, 1
        return node, 0

    return walk_json_strings(payload, redact_value)


def redact_json_local_config(path: Path, source: str | None = None) -> int:
    text = path.read_text(encoding="utf-8")
    relative_source = source or path.name
    text, dev_removed = _strip_dev_only_top_level_json_keys(text)

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{relative_source} is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        if dev_removed:
            path.write_text(text, encoding="utf-8")
        return dev_removed

    redacted_payload, walker_redactions = _redact_json_local_payload(payload, source=relative_source)
    total = dev_removed + walker_redactions
    if total:
        path.write_text(
            json.dumps(redacted_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return total


def redact_json_stage_config(path: Path, source: str | None = None) -> int:
    text = path.read_text(encoding="utf-8")
    relative_source = source or path.name
    text, dev_removed = _strip_dev_only_top_level_json_keys(text)

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{relative_source} is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        if dev_removed:
            path.write_text(text, encoding="utf-8")
        return dev_removed

    redacted_payload, walker_redactions = _redact_json_stage_payload(payload)
    total = dev_removed + walker_redactions
    if total:
        path.write_text(
            json.dumps(redacted_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return total


__all__ = [
    "redact_json_local_config",
    "redact_json_stage_config",
]
