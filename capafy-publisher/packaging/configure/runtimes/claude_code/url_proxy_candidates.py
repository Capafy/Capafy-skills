from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from packaging._shared.common.constants import ANTHROPIC_OFFICIAL_URL
from packaging._shared.common.url_values import normalize_http_url_candidate
from packaging._shared.config_files.dotenv import iter_dotenv_assignments
from packaging.configure.env_values import usable_env_value
from packaging.configure.runtimes.claude_code.auth import CLAUDE_BASE_URL_ENV_KEY

SETTINGS_SCAN_RELPATHS = (
    ".claude/managed-settings.json",
    ".claude/settings.local.json",
    ".claude/settings.json",
)
MODEL_ENV_FIELDS = ("ANTHROPIC_MODEL", "CLAUDE_MODEL")
MODEL_DOTENV_RELPATHS = (".claude/.env", ".env")


@dataclass(frozen=True)
class SettingsModel:
    value: str = ""
    source_relpath: str = ""
    field: str = ""
    kind: str = ""

    def __bool__(self) -> bool:
        return bool(self.value)


@dataclass(frozen=True)
class SettingsUrl:
    value: str
    source_relpath: str = ""
    kind: str = "synthesized"


def _settings_payload(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _settings_file_model(path: Path, relpath: str) -> SettingsModel:
    payload = _settings_payload(path)
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


def resolve_settings_model(
    claude_home: Optional[Path] = None,
    staging_root: Optional[Path] = None,
    process_env: Optional[Mapping[str, str]] = None,
) -> SettingsModel:
    for relpath in SETTINGS_SCAN_RELPATHS:
        path = claude_home / Path(relpath).name if claude_home is not None else Path()
        if path.is_file():
            model = _settings_file_model(path, relpath)
            if model:
                return model
    for path, relpath in (
        (claude_home / ".env" if claude_home is not None else Path(), ".claude/.env"),
        (staging_root / ".env" if staging_root is not None else Path(), ".env"),
    ):
        model = _dotenv_model(path, relpath)
        if model:
            return model
    if process_env is not None:
        for field in MODEL_ENV_FIELDS:
            model = usable_env_value(process_env.get(field, ""))
            if model:
                return SettingsModel(value=model, field=field, kind="process_env")
    return SettingsModel()


def resolve_settings_url(
    claude_home: Optional[Path],
    process_env: Mapping[str, str],
) -> SettingsUrl:
    for relpath in SETTINGS_SCAN_RELPATHS:
        path = claude_home / Path(relpath).name if claude_home is not None else Path()
        if not path.is_file():
            continue
        env_payload = _settings_payload(path).get("env")
        if not isinstance(env_payload, dict):
            continue
        value = normalize_http_url_candidate(
            usable_env_value(env_payload.get(CLAUDE_BASE_URL_ENV_KEY))
        )
        if value:
            return SettingsUrl(value=value, source_relpath=relpath, kind="settings")
    process_value = normalize_http_url_candidate(
        usable_env_value(process_env.get(CLAUDE_BASE_URL_ENV_KEY, ""))
    )
    if process_value:
        return SettingsUrl(value=process_value, kind="process_env")
    return SettingsUrl(value=ANTHROPIC_OFFICIAL_URL)


__all__ = [
    "MODEL_DOTENV_RELPATHS",
    "MODEL_ENV_FIELDS",
    "SETTINGS_SCAN_RELPATHS",
    "SettingsModel",
    "SettingsUrl",
    "resolve_settings_model",
    "resolve_settings_url",
]
