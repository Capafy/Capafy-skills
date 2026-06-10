from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from packaging._shared.config_files.yaml_loader import (
    remove_yaml_object_key_at_path,
    safe_yaml_dumps,
    safe_yaml_loads,
    set_yaml_path_value,
)
from packaging.configure.contracts import SourceKind
from packaging.configure.env_values import env_reference_name

if TYPE_CHECKING:
    from packaging.configure.contracts import PlanField, UrlProxyPair
    from packaging.configure.staging.env_preprocess import RuntimeEnvContext


_CONFIG_REL = ".hermes/config.yaml"
_DOTENV_RELPATHS = (".hermes/.env", ".env")


def _rewrite_yaml_field(staging_root: Path, plan_field: "PlanField") -> bool:
    if plan_field.source_kind != SourceKind.FILE:
        return False
    if str(plan_field.source_relpath or "").strip() != _CONFIG_REL:
        return False
    location = plan_field.location
    if location is None or location.fmt != "yaml":
        return False
    config_path = Path(staging_root) / _CONFIG_REL
    if not config_path.is_file():
        return True
    try:
        payload = safe_yaml_loads(config_path.read_text(encoding="utf-8"))
    except (OSError, RuntimeError, ValueError):
        return True
    changed = set_yaml_path_value(payload, location.key_path, plan_field.placeholder)
    if changed:
        config_path.write_text(safe_yaml_dumps(payload), encoding="utf-8")
    return True


def rewrite_hermes_yaml_pair_fields(staging_root: Path, plan_field: "PlanField", pair: "UrlProxyPair") -> bool:
    _ = pair
    return _rewrite_yaml_field(staging_root, plan_field)


def finalize_hermes_yaml_rewrites(staging_root: Path, pairs: list["UrlProxyPair"]) -> None:
    for pair in pairs:
        if pair.model_field is not None:
            _rewrite_yaml_field(staging_root, pair.model_field)
    _remove_custom_provider_key_env_fields(staging_root)


def resolve_hermes_staged_env_templates(staging_root: Path, *, env_context: "RuntimeEnvContext") -> frozenset[str]:
    config_path = Path(staging_root) / _CONFIG_REL
    if not config_path.is_file():
        return frozenset()
    try:
        payload = safe_yaml_loads(config_path.read_text(encoding="utf-8"))
    except (OSError, RuntimeError, ValueError):
        return frozenset()

    consumed: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if str(key or "").strip() == "api_key":
                    env_name = env_reference_name(str(value or ""))
                    if env_name:
                        consumed.add(env_name)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    if consumed:
        env_context.consume_staged_dotenv_names(
            Path(staging_root),
            relpaths=_DOTENV_RELPATHS,
            names=frozenset(consumed),
        )
    return frozenset(consumed)


def _remove_custom_provider_key_env_fields(staging_root: Path) -> None:
    config_path = Path(staging_root) / _CONFIG_REL
    if not config_path.is_file():
        return
    try:
        payload = safe_yaml_loads(config_path.read_text(encoding="utf-8"))
    except (OSError, RuntimeError, ValueError):
        return
    providers = payload.get("custom_providers")
    if not isinstance(providers, list):
        return
    changed = False
    for index, provider in enumerate(providers):
        if not isinstance(provider, dict):
            continue
        changed = remove_yaml_object_key_at_path(payload, (f"custom_providers[{index}]", "key_env")) or changed
    if changed:
        config_path.write_text(safe_yaml_dumps(payload), encoding="utf-8")


__all__ = [
    "finalize_hermes_yaml_rewrites",
    "resolve_hermes_staged_env_templates",
    "rewrite_hermes_yaml_pair_fields",
]
