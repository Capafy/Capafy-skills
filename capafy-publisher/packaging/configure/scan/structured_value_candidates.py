from __future__ import annotations

import json
import re
from pathlib import PurePosixPath

from packaging._shared.common.constants import STRUCTURED_ASSIGNMENT_PATTERNS
from packaging._shared.common.json_walk import iter_json_string_leaves
from packaging._shared.common.toml_loader import tomllib
from packaging._shared.common.url_values import find_domains
from packaging.configure.sensitive.keywords import (
    contains_explicit_secret_keyword,
    key_tokens,
    normalize_key_name,
)
from packaging.configure.sensitive.literals import (
    extract_assignment_value,
    extract_secret_value,
    infer_managed_value_type,
    looks_like_secret_literal,
    looks_like_url_or_dsn,
)
from packaging.configure.scan.secret_context import CONTEXTUAL_KEY_SECRET_MARKERS

from .candidate_annotation import annotate_candidate
from .structured_scan_policy import (
    STRUCTURED_SCAN_BASENAMES,
    infer_assignment_service,
    should_scan_structured_values,
)
from .support import pick_domain


JSON_STRUCTURED_SCAN_SUFFIXES = {".json", ".jsonc"}
TOML_STRUCTURED_SCAN_SUFFIXES = {".toml"}
YAML_STRUCTURED_SCAN_SUFFIXES = {".yaml", ".yml"}
ENV_NAME_LITERAL_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{1,127}$")


def _extract_local_url(text: str, start: int, end: int, service: str, default_url: str) -> str:
    context = text[max(0, start - 800) : min(len(text), end + 800)]
    domains = find_domains(context)
    return pick_domain(domains, service, default_url)


def _service_from_json_path(relpath: str, path_parts: list[str], key: str, value: str) -> str:
    for part in reversed(path_parts[:-1]):
        if part.startswith("["):
            continue
        cleaned = normalize_key_name(part)
        if cleaned not in {"env", "config", "settings", "options", "credentials", "secrets", "vars", "variables"}:
            return part
    return infer_assignment_service(relpath, key, value)


def _is_contextual_secret_key(path_parts: list[str], key: str) -> bool:
    if "key" not in set(key_tokens(key)) and normalize_key_name(key) != "key":
        return False
    context_tokens = {
        normalize_key_name(part)
        for part in [*path_parts[:-1], *key_tokens(key)]
        if part and not str(part).startswith("[")
    }
    return bool(context_tokens & CONTEXTUAL_KEY_SECRET_MARKERS)


def _collect_leaf_value_candidates(payload: object, relpath: str, text: str) -> list[dict]:
    if not isinstance(payload, (dict, list)):
        return []

    candidates: list[dict] = []
    for path_parts, key, raw_value in iter_json_string_leaves(payload):
        extracted_value = extract_assignment_value(key, raw_value)
        contextual_secret = _is_contextual_secret_key(path_parts, key)
        if extracted_value is None and contextual_secret:
            secret_value = extract_secret_value(key, raw_value)
            if secret_value and looks_like_secret_literal(secret_value):
                extracted_value = secret_value
        if not extracted_value:
            continue
        entry_type = "api_key" if contains_explicit_secret_keyword(key) or contextual_secret else "managed_value"
        value_type = None if entry_type == "api_key" else infer_managed_value_type(key, extracted_value)
        service = _service_from_json_path(relpath, path_parts, key, extracted_value)
        metadata_url = extracted_value.strip() if looks_like_url_or_dsn(extracted_value) else "unknown"
        local_url = metadata_url
        if entry_type == "api_key":
            local_url = _extract_local_url(text, 0, len(text), service, "unknown")
        candidate = annotate_candidate(
            {
                "entry_type": entry_type,
                "field": key,
                "value_type": value_type,
                "value": extracted_value,
                "service": service,
                "default_url": metadata_url,
                "local_url": local_url,
                "source": relpath,
                "source_detail": ".".join(path_parts),
                "env_name": key if ENV_NAME_LITERAL_PATTERN.fullmatch(key) else None,
            },
            relpath,
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def collect_json_value_candidates(text: str, relpath: str, *, enabled: bool = True) -> list[dict]:
    if not enabled:
        return []
    pure = PurePosixPath(relpath)
    basename = pure.name.lower()
    if pure.suffix.lower() not in JSON_STRUCTURED_SCAN_SUFFIXES and basename not in STRUCTURED_SCAN_BASENAMES:
        return []

    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return []
    return _collect_leaf_value_candidates(payload, relpath, text)


def collect_toml_value_candidates(text: str, relpath: str, *, enabled: bool = True) -> list[dict]:
    if not enabled:
        return []
    pure = PurePosixPath(relpath)
    if pure.suffix.lower() not in TOML_STRUCTURED_SCAN_SUFFIXES:
        return []
    try:
        payload = tomllib.loads(text)
    except (tomllib.TOMLDecodeError, ValueError):
        return []
    return _collect_leaf_value_candidates(payload, relpath, text)


def _parse_simple_yaml_mapping(text: str) -> dict:
    root: dict[str, object] = {}
    stack: list[tuple[int, dict[str, object]]] = [(-1, root)]
    pattern = re.compile(r"^(?P<indent>\s*)(?P<key>[A-Za-z_][A-Za-z0-9_.-]{1,120})\s*:\s*(?P<value>.*?)\s*$")
    for raw_line in text.splitlines():
        stripped_line = raw_line.strip()
        if not stripped_line or stripped_line.startswith("#") or stripped_line.startswith("- "):
            continue
        match = pattern.match(raw_line)
        if not match:
            continue
        indent = len(match.group("indent").replace("\t", "    "))
        key = match.group("key")
        raw_value = match.group("value").strip()
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if raw_value in {"", "|", ">"}:
            child: dict[str, object] = {}
            parent[key] = child
            stack.append((indent, child))
            continue
        if not raw_value.startswith(("'", '"')) and " #" in raw_value:
            raw_value = raw_value.split(" #", 1)[0].rstrip()
        parent[key] = raw_value
    return root


def collect_yaml_value_candidates(text: str, relpath: str, *, enabled: bool = True) -> list[dict]:
    if not enabled:
        return []
    pure = PurePosixPath(relpath)
    if pure.suffix.lower() not in YAML_STRUCTURED_SCAN_SUFFIXES:
        return []
    payload = _parse_simple_yaml_mapping(text)
    return _collect_leaf_value_candidates(payload, relpath, text)


def collect_structured_value_candidates(text: str, relpath: str, *, enabled: bool = True) -> list[dict]:
    if not enabled or not should_scan_structured_values(relpath):
        return []
    json_candidates = collect_json_value_candidates(text, relpath, enabled=enabled)
    if json_candidates:
        return json_candidates
    toml_candidates = collect_toml_value_candidates(text, relpath, enabled=enabled)
    if toml_candidates:
        return toml_candidates
    yaml_candidates = collect_yaml_value_candidates(text, relpath, enabled=enabled)
    if yaml_candidates:
        return yaml_candidates
    candidates: list[dict] = []
    cursor = 0
    for line_no, raw_line in enumerate(text.splitlines(keepends=True), start=1):
        line_start = cursor
        line_end = cursor + len(raw_line)
        cursor = line_end
        line = raw_line.rstrip("\r\n")
        for pattern in STRUCTURED_ASSIGNMENT_PATTERNS:
            match = pattern.match(line)
            if not match:
                continue
            key = match.group("key")
            extracted_value = extract_assignment_value(key, match.group("value"))
            if not extracted_value:
                continue
            entry_type = "api_key" if contains_explicit_secret_keyword(key) else "managed_value"
            value_type = None if entry_type == "api_key" else infer_managed_value_type(key, extracted_value)
            service = infer_assignment_service(relpath, key, extracted_value)
            env_name = key if ENV_NAME_LITERAL_PATTERN.fullmatch(key) else None
            metadata_url = "unknown"
            local_url = "unknown"
            if looks_like_url_or_dsn(extracted_value):
                metadata_url = extracted_value.strip()
                local_url = metadata_url or "unknown"
            elif contains_explicit_secret_keyword(key):
                local_url = _extract_local_url(text, line_start, line_end, service, "unknown")
            candidate = annotate_candidate(
                {
                    "entry_type": entry_type,
                    "field": key,
                    "value_type": value_type,
                    "value": extracted_value,
                    "service": service,
                    "default_url": metadata_url or "unknown",
                    "local_url": metadata_url or local_url or "unknown",
                    "source": f"{relpath} line {line_no}",
                    "env_name": env_name,
                },
                relpath,
            )
            if candidate is not None:
                candidates.append(candidate)
            break
    return candidates


__all__ = [
    "collect_json_value_candidates",
    "collect_structured_value_candidates",
    "collect_toml_value_candidates",
    "collect_yaml_value_candidates",
    "infer_assignment_service",
]
