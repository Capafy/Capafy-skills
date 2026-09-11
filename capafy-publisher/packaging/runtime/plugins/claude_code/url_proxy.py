from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from packaging.common.constants import ANTHROPIC_OFFICIAL_URL
from packaging.common.home import current_home_from_env
from packaging.common.url_values import normalize_http_url_candidate
from packaging.config.dotenv import iter_dotenv_assignments
from packaging.runtime.llm.api_formats import PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES
from packaging.runtime.llm.official_providers import ALL_OFFICIAL_PROVIDER_SPECS_BY_FAMILY
from packaging.runtime.contracts import LlmRoute, SourceKind
from packaging.runtime.contracts import RuntimeContract, ScanContext, build_llm_route
from packaging.runtime.plugins.support import invalid_json_config_error, invalid_text_config_error
from packaging.runtime.plugins.support import usable_env_value


CLAUDE_BASE_URL_ENV_KEY = "ANTHROPIC_BASE_URL"
SETTINGS_RELPATH = ".claude/settings.json"
SETTINGS_SCAN_RELPATHS = (
    ".claude/managed-settings.json",
    ".claude/settings.local.json",
    ".claude/settings.json",
)
MODEL_ENV_FIELDS = ("ANTHROPIC_MODEL", "CLAUDE_MODEL")
_SERVICE = "Anthropic"
_API_FORMAT = PLATFORM_API_FORMAT_ANTHROPIC_MESSAGES
CLAUDE_DEFAULT_API_KEY_FIELD = "ANTHROPIC_API_KEY"
_PROVIDER_NAME = ALL_OFFICIAL_PROVIDER_SPECS_BY_FAMILY["anthropic"].provider_name


@dataclass(frozen=True)
class ResolvedSetting:
    value: str = ""
    source_relpath: str = ""
    field: str = ""
    kind: str = ""

    def __bool__(self) -> bool:
        return bool(self.value)


_SettingsPayloads = tuple[tuple[str, dict], ...]


def _settings_payload(path: Path, *, relpath: str) -> dict:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return {}
    except json.JSONDecodeError as exc:
        raise invalid_json_config_error("Claude settings", relpath, exc) from exc
    if not isinstance(payload, dict):
        raise invalid_text_config_error(
            "Claude settings",
            "JSON",
            relpath,
            "root value is not an object",
        )
    return payload


def _load_settings_payloads(claude_home: Optional[Path]) -> _SettingsPayloads:
    if claude_home is None:
        return ()
    return tuple(
        (
            relpath,
            _settings_payload(
                claude_home / Path(relpath).name,
                relpath=relpath,
            ),
        )
        for relpath in SETTINGS_SCAN_RELPATHS
    )


def _settings_file_model(payload: dict, relpath: str) -> ResolvedSetting:
    model = usable_env_value(payload.get("model"))
    if model:
        return ResolvedSetting(
            value=model,
            source_relpath=relpath,
            field="model",
            kind="settings",
        )
    env_payload = payload.get("env")
    if not isinstance(env_payload, dict):
        return ResolvedSetting()
    for field in MODEL_ENV_FIELDS:
        model = usable_env_value(env_payload.get(field))
        if model:
            return ResolvedSetting(
                value=model,
                source_relpath=relpath,
                field=field,
                kind="settings_env",
            )
    return ResolvedSetting()


def _dotenv_model(path: Path, relpath: str) -> ResolvedSetting:
    if not path.is_file():
        return ResolvedSetting()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ResolvedSetting()
    for field, value, _line_number in iter_dotenv_assignments(text):
        if field not in MODEL_ENV_FIELDS:
            continue
        model = usable_env_value(value)
        if model:
            return ResolvedSetting(
                value=model,
                source_relpath=relpath,
                field=field,
                kind="dotenv",
            )
    return ResolvedSetting()


def resolve_settings_model(
    claude_home: Optional[Path] = None,
    staging_root: Optional[Path] = None,
    process_env: Optional[Mapping[str, str]] = None,
    settings_payloads: Optional[_SettingsPayloads] = None,
) -> ResolvedSetting:
    payloads = (
        settings_payloads
        if settings_payloads is not None
        else _load_settings_payloads(claude_home)
    )
    for relpath, payload in payloads:
        model = _settings_file_model(payload, relpath)
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
                return ResolvedSetting(value=model, field=field, kind="process_env")
    return ResolvedSetting()


def resolve_settings_url(
    claude_home: Optional[Path],
    process_env: Mapping[str, str],
    settings_payloads: Optional[_SettingsPayloads] = None,
) -> ResolvedSetting:
    payloads = (
        settings_payloads
        if settings_payloads is not None
        else _load_settings_payloads(claude_home)
    )
    for relpath, payload in payloads:
        env_payload = payload.get("env")
        if not isinstance(env_payload, dict):
            continue
        value = normalize_http_url_candidate(
            usable_env_value(env_payload.get(CLAUDE_BASE_URL_ENV_KEY))
        )
        if value:
            return ResolvedSetting(value=value, source_relpath=relpath, kind="settings")
    process_value = normalize_http_url_candidate(
        usable_env_value(process_env.get(CLAUDE_BASE_URL_ENV_KEY, ""))
    )
    if process_value:
        return ResolvedSetting(value=process_value, kind="process_env")
    return ResolvedSetting(value=ANTHROPIC_OFFICIAL_URL, kind="synthesized")


class ClaudeCodeRuntime(RuntimeContract):
    def os_fallback_environment_names(self) -> frozenset[str]:
        return frozenset((CLAUDE_BASE_URL_ENV_KEY, *MODEL_ENV_FIELDS))

    def routes(self, ctx: ScanContext) -> list[LlmRoute]:
        user_home = ctx.user_home or current_home_from_env()
        claude_home = user_home / ".claude" if user_home is not None else None
        settings_payloads = _load_settings_payloads(claude_home)
        model = resolve_settings_model(
            claude_home,
            ctx.staging_root,
            ctx.process_env,
            settings_payloads,
        )
        url = resolve_settings_url(claude_home, ctx.process_env, settings_payloads)
        return [
            build_llm_route(
                service=_SERVICE,
                group=SETTINGS_RELPATH,
                url=url.value,
                url_field=CLAUDE_BASE_URL_ENV_KEY,
                source_relpath=url.source_relpath or SETTINGS_RELPATH,
                source_kind=(
                    SourceKind.FILE
                    if url.kind == "settings"
                    else SourceKind.PROCESS_ENV
                    if url.kind == "process_env"
                    else SourceKind.SYNTHESIZED
                ),
                model=model.value,
                api_format=_API_FORMAT,
                provider_name=_PROVIDER_NAME,
                api_key_field=CLAUDE_DEFAULT_API_KEY_FIELD,
            )
        ]


__all__ = [
    "ClaudeCodeRuntime",
    "resolve_settings_model",
    "resolve_settings_url",
]
