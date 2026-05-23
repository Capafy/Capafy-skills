from __future__ import annotations

import re

from packaging._shared.common.constants import ENV_REF_PATTERN, STRUCTURED_ASSIGNMENT_PATTERNS
from packaging._shared.common.url_values import find_domains
from packaging.configure.sensitive.keywords import (
    contains_explicit_secret_keyword,
    contains_explicit_value_keyword,
    contains_login_identifier_keyword,
    key_tokens,
    normalize_key_name,
)
from packaging.configure.sensitive.literals import (
    extract_assignment_value,
    looks_like_placeholder_value,
    looks_like_url_or_dsn,
    strip_literal_value,
)

from .support import pick_domain


ENV_NAME_LITERAL_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{1,127}$")
RUNTIME_ENV_DESTRUCTURE_PATTERN = re.compile(
    r"""\{(?P<body>[^{}]{1,4000})\}\s*=\s*(?:process\.env|import\.meta\.env)\b""",
    re.DOTALL,
)
ENV_REFERENCE_VALUE_TOKENS = {
    "app",
    "auth",
    "authorization",
    "base",
    "client",
    "database",
    "db",
    "dsn",
    "endpoint",
    "env",
    "environment",
    "id",
    "key",
    "proxy",
    "secret",
    "tenant",
    "token",
    "url",
    "value",
    "var",
    "variable",
    "webhook",
}


def _extract_local_url(text: str, start: int, end: int, service: str, default_url: str) -> str:
    context = text[max(0, start - 800) : min(len(text), end + 800)]
    domains = find_domains(context)
    return pick_domain(domains, service, default_url)


def collect_env_url_hints(text: str) -> dict[str, str]:
    hints: dict[str, str] = {}
    for line in text.splitlines():
        domains = find_domains(line)
        if not domains:
            continue
        domain = domains[0]
        for match in ENV_REF_PATTERN.finditer(line):
            env_name = next(group for group in match.groups() if group)
            hints.setdefault(env_name, domain)
    return hints


def _looks_like_env_reference_key(key: str) -> bool:
    normalized = normalize_key_name(key)
    tokens = set(key_tokens(key))
    if normalized in {"env", "envkey", "envname", "envvar", "environmentvariable"}:
        return True
    if "env" not in tokens and "environment" not in tokens and not normalized.endswith("env"):
        return False
    if contains_explicit_secret_keyword(key):
        return True
    if contains_explicit_value_keyword(key):
        return True
    if contains_login_identifier_keyword(key):
        return True
    return bool(tokens & ENV_REFERENCE_VALUE_TOKENS)


def _collect_runtime_env_object_mentions(text: str, known_env_names: set[str] | None = None) -> set[str]:
    known = set(known_env_names) if known_env_names else None
    names: set[str] = set()
    for match in RUNTIME_ENV_DESTRUCTURE_PATTERN.finditer(text):
        body = match.group("body")
        for raw_segment in body.split(","):
            segment = raw_segment.strip()
            if not segment or segment.startswith("..."):
                continue
            name_match = re.match(r"([A-Z][A-Z0-9_]*)\b", segment)
            if not name_match:
                continue
            env_name = name_match.group(1)
            if known is not None and env_name not in known:
                continue
            names.add(env_name)
    return names


def _extract_nearby_structured_url_hint(text: str, target_line_no: int) -> str:
    lines = text.splitlines()
    if not lines:
        return "unknown"

    best_distance: int | None = None
    best_url = "unknown"
    start = max(1, target_line_no - 20)
    end = min(len(lines), target_line_no + 20)
    for line_no in range(start, end + 1):
        if line_no == target_line_no:
            continue
        line = lines[line_no - 1]
        for pattern in STRUCTURED_ASSIGNMENT_PATTERNS:
            match = pattern.match(line)
            if not match:
                continue
            key = match.group("key")
            extracted_value = extract_assignment_value(key, match.group("value"))
            if not extracted_value or not looks_like_url_or_dsn(extracted_value):
                continue
            sanitized = extracted_value.strip()
            if not sanitized:
                continue
            distance = abs(line_no - target_line_no)
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_url = sanitized
            break
    return best_url


def collect_referenced_env_names(text: str, known_env_names: set[str] | None = None) -> tuple[set[str], dict[str, str]]:
    names: set[str] = set()
    url_hints: dict[str, str] = {}
    cursor = 0
    for line_no, raw_line in enumerate(text.splitlines(keepends=True), start=1):
        line_start = cursor
        line_end = cursor + len(raw_line)
        cursor = line_end
        line = raw_line.rstrip("\r\n")
        domains = find_domains(line)
        for match in ENV_REF_PATTERN.finditer(line):
            env_name = next(group for group in match.groups() if group)
            names.add(env_name)
            if domains:
                url_hints.setdefault(env_name, domains[0])
        for pattern in STRUCTURED_ASSIGNMENT_PATTERNS:
            match = pattern.match(line)
            if not match:
                continue
            key = match.group("key")
            if not _looks_like_env_reference_key(key):
                break
            env_name = strip_literal_value(match.group("value"))
            if not ENV_NAME_LITERAL_PATTERN.fullmatch(env_name):
                break
            if looks_like_placeholder_value(env_name):
                break
            names.add(env_name)
            local_url = _extract_nearby_structured_url_hint(text, line_no)
            if local_url == "unknown":
                local_url = _extract_local_url(text, line_start, line_end, key, "unknown")
            if local_url != "unknown" and "://" in local_url:
                url_hints.setdefault(env_name, local_url)
            break
    names.update(_collect_runtime_env_object_mentions(text, known_env_names))
    return names, url_hints


__all__ = [
    "collect_env_url_hints",
    "collect_referenced_env_names",
]
