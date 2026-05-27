from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from packaging._shared.common.process_env import collect_publish_process_env
from packaging.configure.dotenv import iter_dotenv_assignments, remove_dotenv_keys_text
from packaging.configure.env_values import usable_env_value


@dataclass
class RuntimeEnvContext:
    process_env: Mapping[str, str]
    _dotenv_values_by_relpath: dict[str, dict[str, str]] = field(default_factory=dict, init=False, repr=False)
    _consumed_dotenv_names_by_relpath: dict[str, set[str]] = field(default_factory=dict, init=False, repr=False)

    def env_for_names(self, names: frozenset[str]) -> dict[str, str]:
        normalized_names = frozenset(name for name in (str(item).strip() for item in names) if name)
        if not normalized_names:
            return {}
        system_env = collect_publish_process_env(names=normalized_names)
        merged = dict(system_env)
        for name, value in (self.process_env or {}).items():
            normalized_name = str(name or "").strip()
            if normalized_name in normalized_names and isinstance(value, str):
                merged[normalized_name] = value
        return merged

    def staged_dotenv_values(
        self,
        staging_root: Path,
        *,
        relpaths: tuple[str, ...],
        names: frozenset[str],
    ) -> dict[str, str]:
        if not names:
            return {}
        result: dict[str, str] = {}
        for relpath in relpaths:
            values = self._dotenv_values(staging_root, relpath)
            for name in names:
                if name in values and name not in result:
                    result[name] = values[name]
        return result

    def staged_dotenv_values_for_consumer(
        self,
        staging_root: Path,
        *,
        consumer_relpath: str,
        names: frozenset[str],
    ) -> dict[str, str]:
        relpaths = _dotenv_relpaths_for_consumer(consumer_relpath)
        return self.staged_dotenv_values(staging_root, relpaths=relpaths, names=names)

    def staged_dotenv_relpaths_for_consumer(self, consumer_relpath: str) -> tuple[str, ...]:
        return _dotenv_relpaths_for_consumer(consumer_relpath)

    def consume_staged_dotenv_names(
        self,
        staging_root: Path,
        *,
        relpaths: tuple[str, ...],
        names: frozenset[str],
    ) -> None:
        if not names:
            return
        for relpath in relpaths:
            values = self._dotenv_values(staging_root, relpath)
            consumed = {name for name in names if name in values}
            if consumed:
                normalized_relpath = _normalize_staged_relpath(relpath)
                if normalized_relpath:
                    self._consumed_dotenv_names_by_relpath.setdefault(normalized_relpath, set()).update(consumed)

    def apply_staged_dotenv_consumption(self, staging_root: Path) -> int:
        rewrites = 0
        for relpath, names in sorted(self._consumed_dotenv_names_by_relpath.items()):
            if not names:
                continue
            path = Path(staging_root) / relpath
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            updated_text, changed = remove_dotenv_keys_text(text, names)
            if not changed:
                continue
            path.write_text(updated_text, encoding="utf-8")
            rewrites += 1
        return rewrites

    def _dotenv_values(self, staging_root: Path, relpath: str) -> dict[str, str]:
        normalized_relpath = _normalize_staged_relpath(relpath)
        if not normalized_relpath:
            return {}
        if normalized_relpath in self._dotenv_values_by_relpath:
            return self._dotenv_values_by_relpath[normalized_relpath]
        path = Path(staging_root) / normalized_relpath
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            values: dict[str, str] = {}
        else:
            values = {}
            for name, value, _line_number in iter_dotenv_assignments(text):
                normalized_value = usable_env_value(value)
                if name not in values and normalized_value:
                    values[name] = normalized_value
        self._dotenv_values_by_relpath[normalized_relpath] = values
        return values


def _normalize_staged_relpath(relpath: str) -> str:
    normalized = str(relpath or "").strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _dotenv_relpaths_for_consumer(consumer_relpath: str) -> tuple[str, ...]:
    normalized = _normalize_staged_relpath(consumer_relpath)
    parts = [part for part in normalized.split("/") if part]
    if parts and parts[0] in {"_scan_only", ".temp"}:
        return ()
    parent_parts = parts[:-1] if parts else []
    relpaths: list[str] = []
    for depth in range(len(parent_parts), -1, -1):
        if depth > 0:
            if parent_parts[0] in {"_scan_only", ".temp"}:
                continue
            relpaths.append("/".join([*parent_parts[:depth], ".env"]))
        else:
            relpaths.append(".env")
    return tuple(relpaths)


def _target_names(env_id: str) -> frozenset[str]:
    normalized = str(env_id or "").strip()
    names: set[str] = {normalized} if normalized else set()
    try:
        from packaging.runtimes.registry import get_target_descriptor

        descriptor = get_target_descriptor(normalized)
    except (ImportError, ValueError):
        return frozenset(names)
    for value in (
        descriptor.target_id,
        descriptor.canonical_name,
        descriptor.profile_env_id,
        descriptor.runtime_generation,
    ):
        name = str(value or "").strip()
        if name:
            names.add(name)
    return frozenset(names)


def preprocess_runtime_env_sources(
    staging_root: Path,
    *,
    env_id: str,
    env_context: RuntimeEnvContext,
) -> frozenset[str]:
    names = _target_names(env_id)
    consumed: set[str] = set()

    if "openclaw" in names:
        from packaging.configure.runtimes.openclaw.provider_rewrite import resolve_openclaw_staged_env_templates

        consumed.update(resolve_openclaw_staged_env_templates(staging_root, env_context=env_context))

    if "claude_code" in names:
        from packaging.configure.runtimes.claude_code.settings_json import preprocess_settings_model_env

        consumed.update(preprocess_settings_model_env(staging_root, env_context=env_context))

    return frozenset(consumed)
