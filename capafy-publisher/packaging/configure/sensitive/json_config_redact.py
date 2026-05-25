from __future__ import annotations
from typing import Optional

import json
from pathlib import Path

from packaging._shared.common.json_walk import walk_json_strings
from packaging._shared.common.local_path_detection import LOCAL_PATH_PLACEHOLDER, looks_like_local_path
from packaging._shared.policies.path_refs import is_packaged_runtime_ref
from packaging.configure.sensitive.keywords import normalize_key_name
from packaging.configure.sensitive.literals import looks_like_platform_managed_placeholder_value
from packaging.configure.sensitive.redact_constants import RUNTIME_LLM_CONFIG_KEYS


_DEV_ONLY_TOP_LEVEL_JSON_KEYS = ("hooks",)


def _is_runtime_llm_config_key(key: str) -> bool:
    return normalize_key_name(key) in RUNTIME_LLM_CONFIG_KEYS


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


def _redact_json_stage_payload(payload: object) -> tuple[object, int]:
    def redact_value(node: str, key_name: Optional[str]) -> tuple[str, int]:
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


def redact_json_stage_config(path: Path, source: Optional[str] = None) -> int:
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
    "redact_json_stage_config",
]
