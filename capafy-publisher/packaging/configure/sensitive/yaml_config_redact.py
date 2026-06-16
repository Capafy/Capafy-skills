from __future__ import annotations
from typing import Any, Optional

from pathlib import Path

from packaging._shared.common.local_path_detection import LOCAL_PATH_PLACEHOLDER, looks_like_local_path
from packaging._shared.config_files.yaml_loader import safe_yaml_dumps, safe_yaml_loads
from packaging._shared.policies.path_refs import is_packaged_runtime_ref
from packaging.configure.sensitive.keywords import normalize_key_name
from packaging.configure.sensitive.literals import looks_like_platform_managed_placeholder_value
from packaging.configure.sensitive.redact_constants import RUNTIME_LLM_CONFIG_KEYS


def _is_runtime_llm_config_key(key: str) -> bool:
    return normalize_key_name(key) in RUNTIME_LLM_CONFIG_KEYS


def _redact_yaml_node(node: Any, key_name: Optional[str] = None) -> tuple[Any, int]:
    if isinstance(node, dict):
        result = {}
        count = 0
        for key, value in node.items():
            updated_value, redactions = _redact_yaml_node(value, str(key))
            result[key] = updated_value
            count += redactions
        return result, count
    if isinstance(node, list):
        values = []
        count = 0
        for value in node:
            updated_value, redactions = _redact_yaml_node(value, key_name)
            values.append(updated_value)
            count += redactions
        return values, count
    if isinstance(node, str):
        if looks_like_platform_managed_placeholder_value(node):
            return node, 0
        if is_packaged_runtime_ref(node):
            return node, 0
        if _is_runtime_llm_config_key(key_name or ""):
            return node, 0
        if looks_like_local_path(node):
            return LOCAL_PATH_PLACEHOLDER, 1
    return node, 0


def redact_yaml_stage_config(path: Path, source: Optional[str] = None) -> int:
    relative_source = source or path.name
    try:
        payload = safe_yaml_loads(path.read_text(encoding="utf-8"))
    except (RuntimeError, ValueError) as exc:
        raise ValueError(f"{relative_source} cannot be parsed as YAML: {exc}") from exc
    if not isinstance(payload, dict):
        return 0
    redacted_payload, redactions = _redact_yaml_node(payload)
    if redactions:
        path.write_text(safe_yaml_dumps(redacted_payload), encoding="utf-8")
    return redactions


__all__ = ["redact_yaml_stage_config"]
