from __future__ import annotations
from typing import Optional

import json
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
from typing import Mapping

from packaging.configure.candidate import Candidate
from packaging.configure.contracts import SourceKind
from packaging.configure.dotenv import iter_dotenv_assignments
from packaging.configure.env_values import usable_env_value
from packaging.configure.runtimes.claude_code.auth import (
    CLAUDE_AUTH_ENV_KEY,
    CLAUDE_AUTH_TOKEN_ENV_KEY,
    CLAUDE_BASE_URL_ENV_KEY,
)

SETTINGS_SCAN_RELPATHS = (
    ".claude/managed-settings.json",
    ".claude/settings.local.json",
    ".claude/settings.json",
)
MODEL_ENV_FIELDS = ("ANTHROPIC_MODEL", "CLAUDE_MODEL")
MODEL_DOTENV_RELPATHS = (".claude/.env", ".env")
API_KEY_FIELD_ORDER = {
    CLAUDE_AUTH_TOKEN_ENV_KEY: 0,
    CLAUDE_AUTH_ENV_KEY: 1,
}
BASE_URL_FIELD_ORDER = {
    CLAUDE_BASE_URL_ENV_KEY: 0,
}

_SETTINGS_SOURCE_ORDER = {
    relpath: index
    for index, relpath in enumerate(SETTINGS_SCAN_RELPATHS)
}


@dataclass(frozen=True)
class SettingsModel:
    value: str = ""
    source_relpath: str = ""
    field: str = ""
    kind: str = ""

    def __bool__(self) -> bool:
        return bool(self.value)


def _settings_file_model(path: Path, relpath: str) -> SettingsModel:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return SettingsModel()
    if not isinstance(payload, dict):
        return SettingsModel()
    model = usable_env_value(payload.get("model"))
    if model:
        return SettingsModel(value=model, source_relpath=relpath, field="model", kind="settings")
    env_payload = payload.get("env")
    if not isinstance(env_payload, dict):
        return SettingsModel()
    for field in MODEL_ENV_FIELDS:
        model = usable_env_value(env_payload.get(field))
        if model:
            return SettingsModel(value=model, source_relpath=relpath, field=field, kind="settings_env")
    return SettingsModel()


def _dotenv_model(path: Path, relpath: str) -> SettingsModel:
    if not path.is_file():
        return SettingsModel()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return SettingsModel()
    for field, value, _line_number in iter_dotenv_assignments(text):
        if field not in MODEL_ENV_FIELDS:
            continue
        model = usable_env_value(value)
        if model:
            return SettingsModel(value=model, source_relpath=relpath, field=field, kind="dotenv")
    return SettingsModel()


def resolve_settings_model(staging_root: Path, process_env: Optional[Mapping[str, str]] = None) -> SettingsModel:
    for relpath in SETTINGS_SCAN_RELPATHS:
        path = staging_root / relpath
        if not path.is_file():
            continue
        model = _settings_file_model(path, relpath)
        if model:
            return model
    for relpath in MODEL_DOTENV_RELPATHS:
        model = _dotenv_model(staging_root / relpath, relpath)
        if model:
            return model
    if process_env is not None:
        for field in MODEL_ENV_FIELDS:
            model = usable_env_value(process_env.get(field, ""))
            if model:
                return SettingsModel(value=model, field=field, kind="process_env")
    return SettingsModel()


def settings_model(staging_root: Path, process_env: Optional[Mapping[str, str]] = None) -> str:
    return resolve_settings_model(staging_root, process_env).value


def candidate_with_model(candidate: Candidate, model: str) -> Candidate:
    extra = dict(candidate.extra)
    extra.setdefault("model", model)
    return replace(candidate, extra=extra)


def candidate_with_settings_model(candidate: Candidate, model: SettingsModel) -> Candidate:
    extra = dict(candidate.extra)
    extra.setdefault("model", model.value)
    if model.kind:
        extra.setdefault(
            "model_source",
            {
                "kind": model.kind,
                "field": model.field,
                "source_relpath": model.source_relpath,
            },
        )
    return replace(candidate, extra=extra)


def annotate_candidates_with_settings_model(
    candidates: list[Candidate],
    staging_root: Path,
    process_env: Optional[Mapping[str, str]] = None,
) -> list[Candidate]:
    model = resolve_settings_model(staging_root, process_env)
    if not model:
        return candidates
    return [candidate_with_settings_model(candidate, model) for candidate in candidates]


def select_preferred_candidate(
    candidates: list[Candidate],
    *,
    roles: set[str],
    field_order: dict[str, int],
) -> Optional[Candidate]:
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
    if candidate.extra.get("configured_auth_key"):
        return (1, 0)
    if candidate.source_kind == SourceKind.FILE:
        return (2, 0)
    if candidate.source_kind == SourceKind.PROCESS_ENV:
        return (3, 0)
    if str(candidate.value or "").strip():
        return (4, 0)
    return (5, 0)


__all__ = [
    "API_KEY_FIELD_ORDER",
    "BASE_URL_FIELD_ORDER",
    "MODEL_DOTENV_RELPATHS",
    "MODEL_ENV_FIELDS",
    "SETTINGS_SCAN_RELPATHS",
    "SettingsModel",
    "candidate_with_settings_model",
    "annotate_candidates_with_settings_model",
    "candidate_with_model",
    "resolve_settings_model",
    "select_preferred_candidate",
    "settings_model",
    "source_priority",
]
