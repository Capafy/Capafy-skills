from __future__ import annotations

import hashlib
import re

from packaging._shared.common.local_path_detection import LOCAL_PATH_PLACEHOLDER, looks_like_local_path
from packaging._shared.policies.path_refs import is_packaged_runtime_ref
from packaging.configure.sensitive.env_config_redact import redact_env_file, redact_env_stage_config
from packaging.configure.sensitive.json_config_redact import redact_json_local_config, redact_json_stage_config
from packaging.configure.sensitive.literals import (
    extract_assignment_value,
    infer_managed_value_type,
    looks_like_platform_managed_placeholder_value,
    strip_literal_value,
)
from packaging.configure.sensitive.placeholders import build_redaction_placeholder
from packaging.configure.sensitive.toml_config_redact import redact_toml_local_config, redact_toml_stage_config


def _split_value_suffix(raw_value: str) -> tuple[str, str]:
    trimmed = raw_value.rstrip()
    suffix = raw_value[len(trimmed) :]
    in_quote: str | None = None
    escaped = False
    comment_index: int | None = None
    for index, char in enumerate(trimmed):
        if in_quote is not None:
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == in_quote:
                in_quote = None
            continue
        if char in {"'", '"'}:
            in_quote = char
            continue
        if char == "#":
            comment_index = index
            break

    if comment_index is not None:
        suffix = trimmed[comment_index:] + suffix
        trimmed = trimmed[:comment_index].rstrip()

    while trimmed.endswith((",", ";")):
        suffix = trimmed[-1] + suffix
        trimmed = trimmed[:-1].rstrip()
    return trimmed, suffix


def _placeholder_literal(raw_value: str, placeholder: str) -> str:
    core, suffix = _split_value_suffix(raw_value)
    if len(core) >= 2 and core[0] == core[-1] and core[0] in {"'", '"'}:
        quote = core[0]
        return f"{quote}{placeholder}{quote}{suffix}"
    return f"{placeholder}{suffix}"


def _looks_like_composite_literal(raw_value: str) -> bool:
    stripped = raw_value.lstrip()
    return stripped.startswith(("[", "{"))


def _stable_local_placeholder(value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8].upper()
    return f"{LOCAL_PATH_PLACEHOLDER}_{digest}"


def _build_assignment_placeholder(
    key: str,
    raw_value: str,
    *,
    source: str,
    source_detail: str,
) -> str | None:
    stripped_value = strip_literal_value(raw_value)
    if looks_like_platform_managed_placeholder_value(stripped_value):
        return None
    if is_packaged_runtime_ref(stripped_value):
        return None
    literal = extract_assignment_value(key, raw_value)
    if literal:
        value_type = infer_managed_value_type(key, literal)
        return build_redaction_placeholder(
            source,
            field=key,
            source_detail=source_detail,
            value_type=value_type,
        )
    if _looks_like_composite_literal(raw_value):
        return None
    if looks_like_local_path(strip_literal_value(raw_value)):
        return LOCAL_PATH_PLACEHOLDER
    return None


def _replace_assignment_value(
    line: str,
    *,
    pattern: re.Pattern[str],
    source: str,
    source_detail: str,
) -> tuple[str, int]:
    match = pattern.match(line)
    if not match:
        return line, 0
    placeholder = _build_assignment_placeholder(
        match.group("key"),
        match.group("value"),
        source=source,
        source_detail=source_detail,
    )
    if not placeholder:
        return line, 0
    value_start = match.start("value")
    value_end = match.end("value")
    return f"{line[:value_start]}{_placeholder_literal(match.group('value'), placeholder)}{line[value_end:]}", 1


def _split_raw_line(raw_line: str) -> tuple[str, str]:
    if raw_line.endswith("\r\n"):
        return raw_line[:-2], "\r\n"
    if raw_line.endswith("\n"):
        return raw_line[:-1], "\n"
    return raw_line, ""


__all__ = [
    "redact_env_file",
    "redact_env_stage_config",
    "redact_json_local_config",
    "redact_json_stage_config",
    "redact_toml_local_config",
    "redact_toml_stage_config",
]
