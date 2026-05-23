from __future__ import annotations

import json
from pathlib import Path

from packaging.configure.candidate import Candidate
from packaging.configure.contracts import SourceKind

SETTINGS_SCAN_RELPATHS = (
    ".claude/managed-settings.json",
    ".claude/settings.local.json",
    ".claude/settings.json",
)
API_KEY_FIELD_ORDER = {
    "ANTHROPIC_AUTH_TOKEN": 0,
    "ANTHROPIC_API_KEY": 1,
}
BASE_URL_FIELD_ORDER = {
    "ANTHROPIC_BASE_URL": 0,
}

_SETTINGS_SOURCE_ORDER = {
    relpath: index
    for index, relpath in enumerate(SETTINGS_SCAN_RELPATHS)
}


def settings_model(staging_root: Path) -> str:
    for relpath in SETTINGS_SCAN_RELPATHS:
        path = staging_root / relpath
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        model = payload.get("model")
        if isinstance(model, str):
            normalized = model.strip()
            if normalized:
                return normalized
    return ""


def candidate_with_model(candidate: Candidate, model: str) -> Candidate:
    extra = dict(candidate.extra)
    extra.setdefault("model", model)
    return Candidate(
        role=candidate.role,
        field=candidate.field,
        value=candidate.value,
        source_kind=candidate.source_kind,
        source_relpath=candidate.source_relpath,
        location=candidate.location,
        extra=extra,
    )


def annotate_candidates_with_settings_model(
    candidates: list[Candidate],
    staging_root: Path,
) -> list[Candidate]:
    model = settings_model(staging_root)
    if not model:
        return candidates
    return [candidate_with_model(candidate, model) for candidate in candidates]


def select_preferred_candidate(
    candidates: list[Candidate],
    *,
    roles: set[str],
    field_order: dict[str, int],
) -> Candidate | None:
    matching = [candidate for candidate in candidates if candidate.role in roles]
    if not matching:
        return None
    non_empty = [candidate for candidate in matching if str(candidate.value or "").strip()]
    if non_empty:
        matching = non_empty
    else:
        synthesized = [candidate for candidate in matching if candidate.role == "synthesized_api_key"]
        if synthesized:
            matching = synthesized
    return min(
        matching,
        key=lambda candidate: (
            source_priority(candidate),
            field_order.get(candidate.field, 99),
            candidate.field,
        ),
    )


def source_priority(candidate: Candidate) -> tuple[int, int]:
    if candidate.source_relpath in _SETTINGS_SOURCE_ORDER:
        return (0, _SETTINGS_SOURCE_ORDER[candidate.source_relpath])
    if candidate.source_kind == SourceKind.FILE:
        return (1, 0)
    if candidate.source_kind == SourceKind.PROCESS_ENV:
        return (2, 0)
    if str(candidate.value or "").strip():
        return (3, 0)
    return (4, 0)


__all__ = [
    "API_KEY_FIELD_ORDER",
    "BASE_URL_FIELD_ORDER",
    "SETTINGS_SCAN_RELPATHS",
    "annotate_candidates_with_settings_model",
    "candidate_with_model",
    "select_preferred_candidate",
    "settings_model",
    "source_priority",
]
