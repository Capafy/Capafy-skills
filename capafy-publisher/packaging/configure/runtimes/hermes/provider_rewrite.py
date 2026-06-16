from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from packaging._shared.config_files.yaml_loader import (
    get_yaml_path_value,
    remove_yaml_object_key_at_path,
    safe_yaml_dumps,
    safe_yaml_mapping_loads,
    set_yaml_path_value,
)
from packaging.configure.contracts import SourceKind
from packaging.configure.env_values import env_reference_name
from packaging.configure.sensitive.literals import looks_like_platform_managed_placeholder_value

if TYPE_CHECKING:
    from packaging.configure.contracts import PlanField, UrlProxyPair
    from packaging.configure.staging.env_preprocess import RuntimeEnvContext


_CONFIG_REL = ".hermes/config.yaml"
_DOTENV_RELPATHS = (".hermes/.env", ".env")


def _load_hermes_config(staging_root: Path, *, required: bool = False) -> dict:
    config_path = Path(staging_root) / _CONFIG_REL
    if not config_path.is_file():
        if required:
            raise ValueError(f"Hermes config.yaml is missing: {_CONFIG_REL}")
        return {}
    try:
        payload = safe_yaml_mapping_loads(config_path.read_text(encoding="utf-8"))
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError(f"Hermes config.yaml parse failed: {_CONFIG_REL}: {exc}") from exc
    return payload


def _rewrite_yaml_field(staging_root: Path, plan_field: "PlanField") -> bool:
    if plan_field.source_kind != SourceKind.FILE:
        return False
    if str(plan_field.source_relpath or "").strip() != _CONFIG_REL:
        return False
    location = plan_field.location
    if location is None or location.fmt != "yaml":
        return False
    config_path = Path(staging_root) / _CONFIG_REL
    payload = _load_hermes_config(staging_root, required=True)
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
    _remove_custom_provider_key_env_fields(staging_root, pairs)


def resolve_hermes_staged_env_templates(staging_root: Path, *, env_context: "RuntimeEnvContext") -> frozenset[str]:
    config_path = Path(staging_root) / _CONFIG_REL
    if not config_path.is_file():
        return frozenset()
    payload = _load_hermes_config(staging_root)

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


def _remove_custom_provider_key_env_fields(staging_root: Path, pairs: list["UrlProxyPair"]) -> None:
    config_path = Path(staging_root) / _CONFIG_REL
    if not config_path.is_file():
        return
    payload = _load_hermes_config(staging_root)
    providers = payload.get("custom_providers")
    if not isinstance(providers, list):
        return
    changed = False
    rewritten_indexes = _rewritten_custom_provider_indexes(pairs)
    for index in rewritten_indexes:
        if index < 0 or index >= len(providers):
            continue
        provider = providers[index]
        if not isinstance(provider, dict):
            continue
        api_key = get_yaml_path_value(payload, (f"custom_providers[{index}]", "api_key"))
        if not looks_like_platform_managed_placeholder_value(str(api_key or "").strip()):
            raise ValueError(
                "Hermes custom provider key_env cannot be removed because api_key was not "
                f"rewritten for custom_providers[{index}]"
            )
        changed = remove_yaml_object_key_at_path(payload, (f"custom_providers[{index}]", "key_env")) or changed
    if changed:
        config_path.write_text(safe_yaml_dumps(payload), encoding="utf-8")


def _rewritten_custom_provider_indexes(pairs: list["UrlProxyPair"]) -> set[int]:
    indexes: set[int] = set()
    for pair in pairs:
        location = pair.key.location
        if pair.key.source_kind != SourceKind.FILE or pair.key.source_relpath != _CONFIG_REL:
            continue
        if location is None or location.fmt != "yaml":
            continue
        key_path = tuple(str(part or "").strip() for part in location.key_path if str(part or "").strip())
        if len(key_path) < 2 or key_path[1] != "api_key":
            continue
        first = key_path[0]
        if not first.startswith("custom_providers[") or not first.endswith("]"):
            continue
        try:
            indexes.add(int(first[len("custom_providers[") : -1]))
        except ValueError:
            continue
    return indexes


__all__ = [
    "finalize_hermes_yaml_rewrites",
    "resolve_hermes_staged_env_templates",
    "rewrite_hermes_yaml_pair_fields",
]
