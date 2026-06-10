from __future__ import annotations
from typing import Optional

from pathlib import PurePosixPath

from packaging._shared.env_profiles import list_profiles


def _build_platform_llm_config_sources() -> dict[str, dict]:
    sources: dict[str, dict] = {}
    for profile in list_profiles():
        env_id = str(profile.get("env_id", "")).strip()
        if not env_id:
            continue
        raw_contract = profile.get("platform_contract", {})
        if not isinstance(raw_contract, dict):
            continue
        config_files = tuple(
            str(item).strip()
            for item in raw_contract.get("config_files", ())
            if isinstance(item, str) and item.strip()
        )
        env_vars: dict[str, tuple[str, str]] = {}
        raw_env_vars = raw_contract.get("env_vars", {})
        if isinstance(raw_env_vars, dict):
            for env_name, raw_spec in raw_env_vars.items():
                if not isinstance(raw_spec, dict):
                    continue
                normalized_env_name = str(env_name or "").strip()
                service = str(raw_spec.get("service", "") or "").strip()
                canonical_url = str(raw_spec.get("canonical_url", "") or "").strip()
                if normalized_env_name and service and canonical_url:
                    env_vars[normalized_env_name] = (service, canonical_url)
        sources[env_id] = {
            "config_files": config_files,
            "env_vars": env_vars,
        }
    return sources


PLATFORM_LLM_CONFIG_SOURCES = _build_platform_llm_config_sources()


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
