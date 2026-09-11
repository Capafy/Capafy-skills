from __future__ import annotations
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - depends on host environment
    yaml = None
    _YAML_IMPORT_ERROR = exc
else:
    _YAML_IMPORT_ERROR = None


def _require_yaml():
    if yaml is None:
        raise RuntimeError("YAML configuration support requires PyYAML") from _YAML_IMPORT_ERROR
    return yaml


def safe_yaml_loads(text: str) -> Any:
    parser = _require_yaml()
    try:
        payload = parser.safe_load(text) or {}
    except Exception as exc:
        yaml_error = getattr(parser, "YAMLError", ())
        if yaml_error and isinstance(exc, yaml_error):
            raise ValueError(f"failed to parse YAML: {exc}") from exc
        raise
    return payload


def safe_yaml_mapping_loads(text: str, *, label: str = "YAML document") -> dict:
    payload = safe_yaml_loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a YAML mapping")
    return payload


__all__ = [
    "safe_yaml_loads",
    "safe_yaml_mapping_loads",
]
