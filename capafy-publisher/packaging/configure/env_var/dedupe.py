from __future__ import annotations

from pathlib import PurePosixPath
from typing import Iterable, Mapping

from packaging.configure.contracts import GenericValue, ReviewedScanBuildInput
from packaging.configure.sensitive.keywords import normalize_key_name


_SETTINGS_ENV_BASENAMES = frozenset({"managed-settings.json", "settings.json", "settings.local.json"})
_RUNTIME_CONFIG_DIRS = frozenset({".claude", ".codex", ".openclaw"})
_ENV_MAPPING_FIELD_PARENTS = frozenset({
    "env",
    "envvars",
    "environment",
    "environmentvariables",
    "environmentvars",
    "vars",
    "variables",
})
_EnvConfigEntry = tuple[str, str]


def _normalize_path(source: object) -> str:
    normalized = str(source or "").strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _references(raw_references: object) -> tuple[str, ...]:
    if not isinstance(raw_references, (list, tuple)):
        return ()
    return tuple(reference for reference in (_normalize_path(item) for item in raw_references) if reference)


def _is_dotenv_source(source: str) -> bool:
    name = PurePosixPath(source).name.lower()
    return name == ".env" or name.startswith(".env.")


def _is_settings_env_source(source: str) -> bool:
    return PurePosixPath(source).name.lower() in _SETTINGS_ENV_BASENAMES


def _runtime_config_scope(source: str) -> str:
    path = PurePosixPath(source)
    if len(path.parts) >= 2 and path.parts[0] in _RUNTIME_CONFIG_DIRS:
        return path.parts[0]
    if _is_settings_env_source(source):
        return path.parent.as_posix()
    return ""


def _dotenv_visible_to_reference(dotenv_source: str, reference: str) -> bool:
    if not reference or reference.startswith(("_scan_only/", ".temp/")):
        return False
    source_parent = PurePosixPath(dotenv_source).parent.as_posix()
    if source_parent == ".":
        return True
    reference_parent = PurePosixPath(reference).parent.as_posix()
    return reference == source_parent or reference_parent == source_parent or reference.startswith(f"{source_parent}/")


def _settings_visible_to_reference(settings_source: str, reference: str) -> bool:
    if not reference:
        return False
    if reference == settings_source:
        return True
    source_scope = _runtime_config_scope(settings_source)
    reference_scope = _runtime_config_scope(reference)
    return bool(source_scope and reference_scope and source_scope == reference_scope)


def _independent_references(raw_references: Iterable[object]) -> tuple[str, ...]:
    return tuple(
        reference
        for reference in (_normalize_path(item) for item in raw_references)
        if reference and not reference.startswith(("_scan_only/", ".temp/"))
    )


def _dotenv_covers_env_references(dotenv_source: str, references: Iterable[object]) -> bool:
    independent = _independent_references(references)
    return bool(independent) and all(
        _dotenv_visible_to_reference(dotenv_source, reference)
        for reference in independent
    )


def _settings_covers_env_references(settings_source: str, references: Iterable[object]) -> bool:
    independent = _independent_references(references)
    if not independent:
        return _runtime_config_scope(settings_source) in _RUNTIME_CONFIG_DIRS
    return all(
        _settings_visible_to_reference(settings_source, reference)
        for reference in independent
    )


def _generic_field_matches_env_var(*, env_field: object, generic_field: object) -> bool:
    env_name = str(env_field or "").strip()
    generic_name = str(generic_field or "").strip()
    if not env_name or not generic_name:
        return False
    if env_name == generic_name:
        return True
    parts = [part for part in generic_name.replace("/", ".").split(".") if part]
    if len(parts) < 2 or parts[-1] != env_name:
        return False
    return normalize_key_name(parts[-2]) in _ENV_MAPPING_FIELD_PARENTS


def _generic_covered_env_var(
    *,
    env_field: object,
    env_references: Iterable[object],
    generic_field: object,
    generic_source: object,
) -> bool:
    if not _generic_field_matches_env_var(env_field=env_field, generic_field=generic_field):
        return False
    source = _normalize_path(generic_source)
    if not source:
        return False
    references = _references(env_references)
    if _is_dotenv_source(source):
        return _dotenv_covers_env_references(source, references)
    if _is_settings_env_source(source):
        return _settings_covers_env_references(source, references)
    return False


def _field_from_reviewed_generic(entry: Mapping[str, object]) -> str:
    field = str(entry.get("field", "") or "").strip()
    if field:
        return field
    source_detail = str(entry.get("source_detail", "") or "")
    for marker in ("env.", "/env/"):
        if marker in source_detail:
            candidate = source_detail.rsplit(marker, 1)[-1].strip().strip("/")
            if candidate:
                return candidate
    return ""


def _generic_value_entry(generic_value: GenericValue) -> _EnvConfigEntry:
    return (str(generic_value.field or "").strip(), _normalize_path(generic_value.source_relpath))


def _reviewed_generic_entry(entry: object) -> _EnvConfigEntry:
    if not isinstance(entry, Mapping):
        return ("", "")
    return (_field_from_reviewed_generic(entry), _normalize_path(entry.get("source")))


def _env_var_covered_by_generic_entries(
    *,
    env_field: object,
    env_references: Iterable[object],
    generic_entries: Iterable[_EnvConfigEntry],
) -> bool:
    normalized_env_field = str(env_field or "").strip()
    if not normalized_env_field:
        return False
    return any(
        _generic_covered_env_var(
            env_field=normalized_env_field,
            env_references=env_references,
            generic_field=generic_field,
            generic_source=generic_source,
        )
        for generic_field, generic_source in generic_entries
    )


def filter_reviewed_input_env_vars_covered_by_generic_values(
    reviewed_input: ReviewedScanBuildInput,
) -> ReviewedScanBuildInput:
    generic_entries = tuple(_generic_value_entry(generic_value) for generic_value in reviewed_input.generic_values)
    env_vars = tuple(
        env_var
        for env_var in reviewed_input.env_vars
        if not _env_var_covered_by_generic_entries(
            env_field=env_var.name,
            env_references=env_var.referenced_in,
            generic_entries=generic_entries,
        )
    )
    if env_vars == reviewed_input.env_vars:
        return reviewed_input
    return ReviewedScanBuildInput(
        url_proxy_pairs=reviewed_input.url_proxy_pairs,
        generic_values=reviewed_input.generic_values,
        env_vars=env_vars,
        excludes=reviewed_input.excludes,
    )


def reviewed_env_var_covered_by_generic_entries(
    env_entry: object,
    generic_entries: Iterable[object],
) -> bool:
    if not isinstance(env_entry, Mapping):
        return False
    return _env_var_covered_by_generic_entries(
        env_field=env_entry.get("field"),
        env_references=env_entry.get("referenced_in"),
        generic_entries=tuple(_reviewed_generic_entry(entry) for entry in generic_entries),
    )


__all__ = [
    "filter_reviewed_input_env_vars_covered_by_generic_values",
    "reviewed_env_var_covered_by_generic_entries",
]
