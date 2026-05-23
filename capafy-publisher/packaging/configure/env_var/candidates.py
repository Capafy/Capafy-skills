from __future__ import annotations

from packaging.configure.contracts import PROCESS_ENV_SOURCE
from packaging.configure.env_var.names import iter_related_process_env_names
from packaging.configure.sensitive.keywords import contains_explicit_secret_keyword
from packaging.configure.sensitive.literals import (
    extract_assignment_value,
    infer_managed_value_type,
    looks_like_url_or_dsn,
)
from packaging.configure.scan.candidate_annotation import annotate_candidate
from packaging.configure.scan.structured_scan_policy import infer_assignment_service


def _resolve_process_env_url(
    env_name: str,
    process_env: dict[str, str],
    known_env_url_hints: dict[str, str],
) -> str:
    hinted = known_env_url_hints.get(env_name)
    if hinted:
        return hinted
    for peer_name in sorted(iter_related_process_env_names(env_name)):
        raw_value = process_env.get(peer_name)
        if raw_value is None:
            continue
        extracted_value = extract_assignment_value(peer_name, raw_value)
        if not extracted_value or not looks_like_url_or_dsn(extracted_value):
            continue
        sanitized = extracted_value.strip()
        if sanitized:
            return sanitized
    return "unknown"


def _build_process_env_candidate(
    env_name: str,
    raw_value: str,
    process_env: dict[str, str],
    known_env_url_hints: dict[str, str],
) -> tuple[dict | None, dict[str, str], dict[str, str]]:
    extracted_value = extract_assignment_value(env_name, raw_value)
    if not extracted_value:
        return None, {}, {}

    entry_type = "api_key" if contains_explicit_secret_keyword(env_name) else "managed_value"
    value_type = None if entry_type == "api_key" else infer_managed_value_type(env_name, extracted_value)
    service = infer_assignment_service(PROCESS_ENV_SOURCE, env_name, extracted_value)
    default_url = "unknown"
    local_url = "unknown"
    env_url_hints: dict[str, str] = {}
    value_url_hints: dict[str, str] = {}

    if looks_like_url_or_dsn(extracted_value):
        sanitized = extracted_value.strip() or "unknown"
        default_url = sanitized
        local_url = sanitized
        if sanitized != "unknown":
            env_url_hints[env_name] = sanitized
            value_url_hints[extracted_value] = sanitized
    elif entry_type == "api_key":
        local_url = _resolve_process_env_url(env_name, process_env, known_env_url_hints)
        if local_url != "unknown":
            env_url_hints[env_name] = local_url

    candidate = annotate_candidate(
        {
            "entry_type": entry_type,
            "field": env_name,
            "value_type": value_type,
            "value": extracted_value,
            "service": service,
            "default_url": default_url,
            "local_url": local_url,
            "source": PROCESS_ENV_SOURCE.strip(),
            "env_name": env_name,
        },
        PROCESS_ENV_SOURCE,
    )
    return candidate, env_url_hints, value_url_hints


def collect_process_env_candidates(
    process_env: dict[str, str],
    referenced_env_names: set[str],
    known_env_url_hints: dict[str, str],
) -> tuple[list[dict], dict[str, str], dict[str, str]]:
    referenced_names = {name for name in referenced_env_names if name in process_env}
    hinted_names = {name for name in known_env_url_hints if name in process_env}
    related_names: set[str] = set()
    for env_name in referenced_names | hinted_names:
        related_names.update(name for name in iter_related_process_env_names(env_name) if name in process_env)
    confirmed_names = referenced_names | hinted_names | related_names

    candidates: list[dict] = []
    env_url_hints: dict[str, str] = {}
    value_url_hints: dict[str, str] = {}
    for env_name in sorted(confirmed_names):
        candidate, candidate_env_hints, candidate_value_hints = _build_process_env_candidate(
            env_name,
            process_env[env_name],
            process_env,
            {**known_env_url_hints, **env_url_hints},
        )
        if candidate is None:
            continue
        candidates.append(candidate)
        for hint_name, hint_value in candidate_env_hints.items():
            env_url_hints.setdefault(hint_name, hint_value)
        for hint_value, url in candidate_value_hints.items():
            value_url_hints.setdefault(hint_value, url)
    return candidates, env_url_hints, value_url_hints


__all__ = ["collect_process_env_candidates"]
