from __future__ import annotations

from typing import Any, Optional

from packaging.configure.sensitive.keywords import contains_explicit_secret_keyword
from packaging.configure.sensitive.literals import (
    looks_like_platform_managed_placeholder_value,
    looks_like_placeholder_value,
    looks_like_secret_literal,
)


_METADATA_VALUE_KEYS = {
    "api_format",
    "field",
    "masked",
    "model",
    "placeholder",
    "reason",
    "source",
    "source_detail",
    "use",
    "value_type",
}
_API_KEY_PATH_PARTS = {"api_key", "apikey", "apiKey"}


def _format_path(path: list[object]) -> str:
    result = ""
    for part in path:
        if isinstance(part, int):
            result += f"[{part}]"
            continue
        text = str(part)
        result = f"{result}.{text}" if result else text
    return result


def _path_has_part(path: list[object], names: set[str]) -> bool:
    normalized_names = {name.casefold() for name in names}
    return any(isinstance(part, str) and part.casefold() in normalized_names for part in path)


def _safe_text(value: object) -> str:
    return str(value or "").strip()


def _is_placeholder_or_masked(value: str) -> bool:
    if not value:
        return True
    if looks_like_platform_managed_placeholder_value(value) or looks_like_placeholder_value(value):
        return True
    return "*" in value or "…" in value


def _field_name(parent: dict[str, Any]) -> str:
    return _safe_text(parent.get("field"))


def _secret_context(path: list[object], key: str, parent: dict[str, Any]) -> bool:
    if _path_has_part(path[:-1], _API_KEY_PATH_PARTS):
        return True
    if contains_explicit_secret_keyword(key):
        return True
    return contains_explicit_secret_keyword(_field_name(parent))


def _finding(kind: str, path: list[object], parent: dict[str, Any]) -> dict[str, str]:
    result = {
        "kind": kind,
        "path": _format_path(path),
    }
    field = _field_name(parent)
    if field:
        result["field"] = field
    placeholder = _safe_text(parent.get("placeholder"))
    if placeholder:
        result["placeholder"] = placeholder
    return result


def _inspect_string(
    *,
    path: list[object],
    key: str,
    value: str,
    parent: dict[str, Any],
    has_generic_entries: bool,
) -> Optional[dict[str, str]]:
    if key in _METADATA_VALUE_KEYS or _is_placeholder_or_masked(value):
        return None
    if _path_has_part(path[:-1], {"generic"}) and key == "value":
        return _finding("plaintext_value", path, parent)
    if (key == "value" or contains_explicit_secret_keyword(key)) and _secret_context(path, key, parent):
        if looks_like_secret_literal(value):
            kind = "plaintext_value" if has_generic_entries else "api_key"
            return _finding(kind, path, parent)
    return None


def find_plaintext_required_credentials(payload: object) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    has_generic_entries = (
        isinstance(payload, dict)
        and isinstance(payload.get("generic"), list)
        and any(isinstance(item, dict) for item in payload.get("generic", []))
    )

    def walk(node: object, path: list[object], parent: dict[str, Any]) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                next_path = [*path, str(key)]
                if isinstance(value, str):
                    finding = _inspect_string(
                        path=next_path,
                        key=str(key),
                        value=value.strip(),
                        parent=node,
                        has_generic_entries=has_generic_entries,
                    )
                    if finding is not None:
                        findings.append(finding)
                else:
                    walk(value, next_path, node)
            return
        if isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, [*path, index], parent)

    walk(payload, [], {})
    return findings


__all__ = ["find_plaintext_required_credentials"]
