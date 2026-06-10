from __future__ import annotations
from typing import Optional, TYPE_CHECKING

import json
from pathlib import Path

from packaging.configure.runtimes.openclaw.official_providers import (
    match_openclaw_builtin_model_provider,
)
from packaging.configure.runtimes.openclaw.provider_env_templates import (
    OPENCLAW_CONFIG_REL_SOURCE as _OPENCLAW_CONFIG_REL_SOURCE,
    collect_openclaw_staged_dotenv_env,
    drop_consumed_config_env,
    materialize_official_provider_env_keys,
    materialize_provider_env_references,
    resolve_openclaw_config_env,
    resolve_openclaw_staged_env_templates,
)
from packaging.configure.runtimes.openclaw.provider_payloads import (
    canonicalize_official_provider_aliases,
    discover_model_template,
    ensure_provider_payload,
    provider_name_for_spec,
)
from packaging.configure.runtimes.openclaw.provider_usage import (
    path_likely_contains_openclaw_model_ref,
)
from packaging._shared.config_files.json_io import clone_json_value

if TYPE_CHECKING:
    from packaging.configure.staging.env_preprocess import RuntimeEnvContext


_DEFAULT_MODELS_MODE = "merge"


def _rewrite_builtin_model_refs(
    node: object,
    *,
    path_parts: tuple[str, ...],
    providers: dict[str, object],
    assigned_names: dict[str, str],
    model_template: Optional[dict[str, object]],
) -> tuple[object, int]:
    if isinstance(node, dict):
        lowered_path = tuple(part.lower() for part in path_parts[:2])
        if lowered_path == ("models", "providers"):
            return clone_json_value(node), 0
        updated: dict[str, object] = {}
        rewrites = 0
        for key, value in node.items():
            next_value, next_rewrites = _rewrite_builtin_model_refs(
                value,
                path_parts=(*path_parts, str(key)),
                providers=providers,
                assigned_names=assigned_names,
                model_template=model_template,
            )
            updated[str(key)] = next_value
            rewrites += next_rewrites
        return updated, rewrites

    if isinstance(node, list):
        updated_items: list[object] = []
        rewrites = 0
        for index, value in enumerate(node):
            next_value, next_rewrites = _rewrite_builtin_model_refs(
                value,
                path_parts=(*path_parts, str(index)),
                providers=providers,
                assigned_names=assigned_names,
                model_template=model_template,
            )
            updated_items.append(next_value)
            rewrites += next_rewrites
        return updated_items, rewrites

    if not isinstance(node, str) or not path_likely_contains_openclaw_model_ref(path_parts):
        return node, 0

    matched = match_openclaw_builtin_model_provider(node)
    if matched is None:
        return node, 0
    spec, model_name = matched
    if not model_name:
        return node, 0

    provider_name = provider_name_for_spec(
        spec,
        providers,
        assigned_names,
    )
    ensure_provider_payload(
        providers,
        provider_name,
        spec=spec,
        model_name=model_name,
        model_template=model_template,
    )
    return f"{provider_name}/{model_name}", 1


def rewrite_openclaw_builtin_models_as_explicit_providers(
    config_text: str,
    *,
    staging_root: Path,
    env_context: "RuntimeEnvContext",
) -> tuple[str, int]:
    try:
        payload = json.loads(config_text)
    except json.JSONDecodeError:
        return config_text, 0
    if not isinstance(payload, dict):
        return config_text, 0

    dotenv_env = collect_openclaw_staged_dotenv_env(staging_root, config_text, env_context=env_context)
    config_env = resolve_openclaw_config_env(
        payload=payload,
        dotenv_env=dotenv_env,
    )
    consumed_env_names: set[str] = set()

    model_template = discover_model_template(payload)
    models = payload.get("models")
    if not isinstance(models, dict):
        models = {}
        payload["models"] = models
    providers = models.get("providers")
    if not isinstance(providers, dict):
        providers = {}
        models["providers"] = providers
    alias_rewrites = canonicalize_official_provider_aliases(providers)

    assigned_names: dict[str, str] = {}
    rewritten_payload, rewrite_count = _rewrite_builtin_model_refs(
        payload,
        path_parts=(),
        providers=providers,
        assigned_names=assigned_names,
        model_template=model_template,
    )
    official_key_rewrites, provider_key_consumed_env_names = materialize_official_provider_env_keys(
        providers,
        config_env,
    )
    provider_ref_rewrites, provider_ref_consumed_env_names = materialize_provider_env_references(providers, config_env)
    consumed_env_names.update(provider_key_consumed_env_names)
    consumed_env_names.update(provider_ref_consumed_env_names)
    provider_key_rewrites = official_key_rewrites + provider_ref_rewrites
    if consumed_env_names:
        env_context.consume_staged_dotenv_names(
            staging_root,
            relpaths=env_context.staged_dotenv_relpaths_for_consumer(_OPENCLAW_CONFIG_REL_SOURCE),
            names=frozenset(consumed_env_names),
        )
    if provider_key_rewrites or alias_rewrites:
        rewritten_payload["models"] = clone_json_value(models)
    if consumed_env_names:
        drop_consumed_config_env(rewritten_payload, consumed_env_names)
    if rewrite_count <= 0:
        total_rewrites = provider_key_rewrites + alias_rewrites
        if total_rewrites <= 0:
            return config_text, 0
        return json.dumps(rewritten_payload, ensure_ascii=False, indent=2) + "\n", total_rewrites
    if not str(models.get("mode", "")).strip():
        models["mode"] = _DEFAULT_MODELS_MODE
    rewritten_payload["models"] = clone_json_value(models)
    return json.dumps(rewritten_payload, ensure_ascii=False, indent=2) + "\n", (
        rewrite_count + provider_key_rewrites + alias_rewrites
    )


__all__ = [
    "resolve_openclaw_staged_env_templates",
    "rewrite_openclaw_builtin_models_as_explicit_providers",
]
