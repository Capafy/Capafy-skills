from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any, Mapping

from packaging._shared.common.url_values import normalize_http_url_candidate
from packaging.configure.candidate import Candidate
from packaging.configure.contracts import FieldLocation, SourceKind
from packaging.configure.dotenv import iter_dotenv_assignments
from packaging.configure.env_values import usable_process_env_value
from packaging.configure.sensitive.literals import looks_like_platform_managed_placeholder_value

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UrlProxyFieldSet:

    api_key_fields: frozenset[str]
    base_url_fields: frozenset[str]

    @property
    def known_names(self) -> frozenset[str]:
        return self.api_key_fields | self.base_url_fields




def scan_dotenv(
    file_path: Path,
    relpath: str,
    *,
    fields: UrlProxyFieldSet,
) -> list[Candidate]:
    if not file_path.is_file():
        return []
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        return []
    if not text.strip():
        return []

    candidates: list[Candidate] = []
    occurrence_counters: dict[tuple[str, str], int] = {}
    for key, value, line_number in iter_dotenv_assignments(text):
        if not value or looks_like_platform_managed_placeholder_value(value):
            continue

        if key in fields.api_key_fields:
            occurrence_key = ("api_key", key)
            occurrence_counters[occurrence_key] = occurrence_counters.get(occurrence_key, 0) + 1
            candidates.append(Candidate(
                role="api_key", field=key, value=value,
                source_kind=SourceKind.FILE, source_relpath=relpath,
                location=FieldLocation(
                    fmt="dotenv",
                    occurrence_index=occurrence_counters[occurrence_key],
                    line_number=line_number,
                ),
            ))
        elif key in fields.base_url_fields:
            normalized_url = normalize_http_url_candidate(value)
            if normalized_url:
                occurrence_key = ("base_url", key)
                occurrence_counters[occurrence_key] = occurrence_counters.get(occurrence_key, 0) + 1
                candidates.append(Candidate(
                    role="base_url", field=key, value=normalized_url,
                    source_kind=SourceKind.FILE, source_relpath=relpath,
                    location=FieldLocation(
                        fmt="dotenv",
                        occurrence_index=occurrence_counters[occurrence_key],
                        line_number=line_number,
                    ),
                ))

    return candidates




def scan_json_config(
    file_path: Path,
    relpath: str,
    *,
    fields: UrlProxyFieldSet,
    excluded_prefixes: tuple[str, ...] = (),
) -> list[Candidate]:
    if not file_path.is_file():
        return []
    try:
        text = file_path.read_text(encoding="utf-8")
        payload = json.loads(text)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []

    candidates: list[Candidate] = []
    seen: set[tuple[str, str]] = set()

    def _record(role: str, field: str, value: str, pointer: str) -> None:
        identity = (field, pointer)
        if identity in seen:
            return
        seen.add(identity)
        candidates.append(Candidate(
            role=role, field=field, value=value.strip(),
            source_kind=SourceKind.FILE, source_relpath=relpath,
            location=FieldLocation(fmt="json", json_pointer=pointer),
        ))

    def _walk(d: dict[str, Any], pointer: str = "") -> None:
        for key, value in d.items():
            current = f"{pointer}/{key}" if pointer else f"/{key}"
            parts = [p for p in current.split("/") if p]
            if parts and parts[0] in excluded_prefixes:
                continue
            if isinstance(value, str) and value.strip():
                if looks_like_platform_managed_placeholder_value(value):
                    continue
                if key in fields.api_key_fields:
                    _record("api_key", key, value, current)
                elif key in fields.base_url_fields:
                    normalized_url = normalize_http_url_candidate(value.strip())
                    if normalized_url:
                        _record("base_url", key, normalized_url, current)
            elif isinstance(value, dict):
                _walk(value, current)

    _walk(payload)


    env_payload = payload.get("env")
    if isinstance(env_payload, dict):
        for key, value in env_payload.items():
            if not isinstance(value, str) or not value.strip():
                continue
            if looks_like_platform_managed_placeholder_value(value):
                continue
            pointer = f"/env/{key}"
            if key in fields.api_key_fields:
                _record("api_key", key, value, pointer)
            elif key in fields.base_url_fields:
                normalized_url = normalize_http_url_candidate(value.strip())
                if normalized_url:
                    _record("base_url", key, normalized_url, pointer)

    return candidates




def resolve_process_env_refs(
    staging_root: Path,
    process_env: Mapping[str, str],
    *,
    existing_fields: set[str],
    fields: UrlProxyFieldSet,
) -> list[Candidate]:
    from packaging._shared.common.fs import iter_workspace_files, read_text
    from packaging.configure.scan.env_reference_scan import collect_referenced_env_names

    referenced: set[str] = set()
    for path in iter_workspace_files(staging_root, skip_system=True):
        try:
            rel = path.relative_to(staging_root).as_posix()
        except ValueError:
            continue
        if rel == "_scan_only" or rel.startswith("_scan_only/"):
            continue
        text, _ = read_text(path)
        if not text:
            continue
        local_names, _ = collect_referenced_env_names(text, fields.known_names)
        referenced.update(local_names & fields.known_names)

    candidates: list[Candidate] = []
    for env_name in sorted(referenced - existing_fields):
        actual_value = usable_process_env_value(process_env, env_name)
        role = "base_url" if env_name in fields.base_url_fields else "api_key"
        if role == "base_url":
            if not actual_value or not normalize_http_url_candidate(actual_value):
                continue
        candidates.append(Candidate(
            role=role, field=env_name, value=actual_value,
            source_kind=SourceKind.PROCESS_ENV, source_relpath="",
            location=None,
            extra={"declarative_reference": True},
        ))
    return candidates


__all__ = [
    "UrlProxyFieldSet",
    "resolve_process_env_refs",
    "scan_dotenv",
    "scan_json_config",
]
