from __future__ import annotations
from typing import Optional

from pathlib import PurePosixPath

from packaging._shared.common.constants import (
    ANTHROPIC_OFFICIAL_URL,
    OPENAI_OFFICIAL_URL_V1,
)


PLATFORM_LLM_CONFIG_SOURCES = {
    "claude_code": {
        "config_files": (
            ".claude/.claude.json",
            ".claude/settings.json",
            ".claude/settings.local.json",
            ".claude/managed-settings.json",
            "_scan_only/.claude/.claude.json",
            "_scan_only/.claude/settings.json",
            "_scan_only/.claude/settings.local.json",
            "_scan_only/.claude/managed-settings.json",
        ),
        "env_vars": {
            "ANTHROPIC_API_KEY": ("Anthropic", ANTHROPIC_OFFICIAL_URL),
            "ANTHROPIC_AUTH_TOKEN": ("Anthropic", ANTHROPIC_OFFICIAL_URL),
            "ANTHROPIC_BASE_URL": ("Anthropic", ANTHROPIC_OFFICIAL_URL),
        },
    },
    "codex": {
        "config_files": (
            ".codex/config.toml",
            "_scan_only/.codex/config.toml",
        ),
        "env_vars": {
            "OPENAI_API_KEY": ("OpenAI", OPENAI_OFFICIAL_URL_V1),
            "OPENAI_BASE_URL": ("OpenAI", OPENAI_OFFICIAL_URL_V1),
        },
    },
    "openclaw": {
        "config_files": (
            ".openclaw/openclaw.json",
            ".openclaw/agents/main/agent/auth-profiles.json",
            "_scan_only/.openclaw/agents/main/agent/auth-profiles.json",
        ),
        "env_vars": {},
    },
}


def _normalize_relpath(relpath: str) -> str:
    return PurePosixPath(str(relpath or "").strip() or ".").as_posix().lstrip("./")


def _contract_key_for_target(target_name: Optional[str]) -> str:
    normalized = str(target_name or "").strip()
    if not normalized or normalized in PLATFORM_LLM_CONFIG_SOURCES:
        return normalized
    try:
        from packaging.runtimes.registry import get_target_descriptor

        canonical_name = str(get_target_descriptor(normalized).canonical_name or "").strip()
    except ValueError:
        return normalized
    return canonical_name if canonical_name in PLATFORM_LLM_CONFIG_SOURCES else normalized


def is_platform_contract_file(relpath: str, *, target_name: Optional[str]) -> bool:
    target_contract = PLATFORM_LLM_CONFIG_SOURCES.get(_contract_key_for_target(target_name), {})
    if not isinstance(target_contract, dict):
        return False
    normalized_relpath = _normalize_relpath(relpath)
    for suffix in target_contract.get("config_files", ()):
        normalized_suffix = _normalize_relpath(suffix)
        if normalized_relpath == normalized_suffix or normalized_relpath.endswith(f"/{normalized_suffix}"):
            return True
    return False


def collect_platform_env_url_hints(
    *,
    target_name: Optional[str],
    referenced_env_names: Optional[set[str]] = None,
    require_referenced_env_names: bool = False,
) -> dict[str, str]:
    target_contract = PLATFORM_LLM_CONFIG_SOURCES.get(_contract_key_for_target(target_name), {})
    if not isinstance(target_contract, dict):
        return {}
    known_names = {
        str(name).strip()
        for name in (referenced_env_names or set())
        if str(name).strip()
    }
    if require_referenced_env_names and not known_names:
        return {}
    hints: dict[str, str] = {}
    for env_name, spec in target_contract.get("env_vars", {}).items():
        if (known_names or require_referenced_env_names) and env_name not in known_names:
            continue
        if not isinstance(spec, tuple) or len(spec) != 2:
            continue
        _service, canonical_url = spec
        if canonical_url:
            hints[env_name] = canonical_url
    return hints


__all__ = [
    "PLATFORM_LLM_CONFIG_SOURCES",
    "collect_platform_env_url_hints",
    "is_platform_contract_file",
]
