from __future__ import annotations

from functools import lru_cache
from importlib import import_module

from packaging._shared.runtimes.contracts import (
    OPENCLAW_LEGACY_TARGET,
    OPENCLAW_MODERN_TARGET,
    RuntimeAdapter,
    TargetDescriptor,
)


_CODEX_RUNTIME_GENERATION = "codex_standalone"
_HERMES_RUNTIME_GENERATION = "hermes_v1"
_OPENCLAW_PROVIDER_GROUP_PREFIX = ".openclaw/openclaw.json#models.providers."


def _make_review_consistency_hook(module_path: str):
    def validate_review_consistency(staging_root, *, reviewed_scan):
        validate = import_module(module_path).validate_review_consistency
        validate(staging_root, reviewed_scan=reviewed_scan)

    return validate_review_consistency


def _runtime_field_source(field_obj) -> str:
    source_identity = getattr(field_obj, "source_identity", None)
    if callable(source_identity):
        return str(source_identity() or "").strip()
    return str(getattr(field_obj, "source_relpath", "") or "").strip()


def _runtime_field_source_detail(field_obj) -> str:
    source_detail_identity = getattr(field_obj, "source_detail_identity", None)
    if callable(source_detail_identity):
        return str(source_detail_identity() or "").strip()
    return ""


def _runtime_field_original_value(field_obj) -> str:
    return str(getattr(field_obj, "original_value", "") or "").strip()


def _codex_descriptors() -> tuple[TargetDescriptor, ...]:
    return (
        TargetDescriptor(
            target_id="codex",
            canonical_name="codex",
            profile_env_id="codex",
            runtime_generation=_CODEX_RUNTIME_GENERATION,
        ),
    )


def _claude_code_descriptors() -> tuple[TargetDescriptor, ...]:
    return (
        TargetDescriptor(
            target_id="claude_code",
            canonical_name="claude_code",
            profile_env_id="claude_code",
        ),
    )


def _hermes_descriptors() -> tuple[TargetDescriptor, ...]:
    return (
        TargetDescriptor(
            target_id="hermes",
            canonical_name="hermes",
            profile_env_id="hermes",
            runtime_generation=_HERMES_RUNTIME_GENERATION,
        ),
    )


def _openclaw_descriptors() -> tuple[TargetDescriptor, ...]:
    return (
        TargetDescriptor(
            target_id="openclaw",
            canonical_name="openclaw",
        ),
        TargetDescriptor(
            target_id=OPENCLAW_LEGACY_TARGET,
            canonical_name="openclaw",
            runtime_generation=OPENCLAW_LEGACY_TARGET,
            runtime_variant="legacy",
        ),
        TargetDescriptor(
            target_id=OPENCLAW_MODERN_TARGET,
            canonical_name="openclaw",
            runtime_generation=OPENCLAW_MODERN_TARGET,
            runtime_variant="modern",
        ),
    )


def _codex_target_factory(descriptor: TargetDescriptor, profile: dict):
    CodexTarget = import_module("packaging.runtimes.codex.target").CodexTarget
    return CodexTarget(profile)


def _claude_code_target_factory(descriptor: TargetDescriptor, profile: dict):
    ClaudeCodeTarget = import_module("packaging.runtimes.claude_code.target").ClaudeCodeTarget
    return ClaudeCodeTarget(profile)


def _hermes_target_factory(descriptor: TargetDescriptor, profile: dict):
    HermesTarget = import_module("packaging.runtimes.hermes.target").HermesTarget
    return HermesTarget(profile)


def _openclaw_target_factory(descriptor: TargetDescriptor, profile: dict):
    openclaw_target = import_module("packaging.runtimes.openclaw.target")
    if descriptor.runtime_variant == "legacy":
        return openclaw_target.LEGACY_TARGET
    if descriptor.runtime_variant == "modern":
        return openclaw_target.MODERN_TARGET
    raise ValueError(f"{descriptor.target_id} is missing openclaw runtime_variant, so the target cannot be built")


def _codex_url_proxy_runtime_factory():
    CodexRuntime = import_module("packaging.configure.runtimes.codex.url_proxy").CodexRuntime
    return CodexRuntime()


def _claude_code_url_proxy_runtime_factory():
    ClaudeCodeRuntime = import_module("packaging.configure.runtimes.claude_code.url_proxy").ClaudeCodeRuntime
    return ClaudeCodeRuntime()


def _hermes_url_proxy_runtime_factory():
    HermesRuntime = import_module("packaging.configure.runtimes.hermes.url_proxy").HermesRuntime
    return HermesRuntime()


def _openclaw_url_proxy_runtime_factory():
    OpenClawRuntime = import_module("packaging.configure.runtimes.openclaw").OpenClawRuntime
    return OpenClawRuntime()


def _claude_code_preprocess_env_sources(staging_root, *, env_context):
    settings_json = import_module("packaging.configure.runtimes.claude_code.settings_json")
    settings_json.prune_settings_proxy_env_sources(staging_root)
    return settings_json.preprocess_settings_model_env(staging_root, env_context=env_context)


def _hermes_preprocess_env_sources(staging_root, *, env_context):
    resolve_templates = import_module(
        "packaging.configure.runtimes.hermes.provider_rewrite"
    ).resolve_hermes_staged_env_templates
    return frozenset(resolve_templates(staging_root, env_context=env_context))


def _openclaw_preprocess_env_sources(staging_root, *, env_context):
    resolve_templates = import_module(
        "packaging.configure.runtimes.openclaw.provider_rewrite"
    ).resolve_openclaw_staged_env_templates
    return frozenset(resolve_templates(staging_root, env_context=env_context))


def _claude_code_owns_structured_pair(pair) -> bool:
    settings_relpaths = import_module(
        "packaging.configure.runtimes.claude_code.url_proxy_candidates"
    ).SETTINGS_SCAN_RELPATHS
    key_source = str(getattr(pair.key, "source_relpath", "") or "").strip()
    url_source = str(getattr(pair.url, "source_relpath", "") or "").strip()
    return key_source in settings_relpaths or url_source in settings_relpaths


def _hermes_owns_structured_pair(pair) -> bool:
    group = str(getattr(pair, "group", "") or "").strip()
    return any(
        group.startswith(prefix)
        for prefix in (
            ".hermes/config.yaml#model",
            ".hermes/config.yaml#auxiliary.",
            ".hermes/config.yaml#delegation",
            ".hermes/config.yaml#fallback_providers[",
            ".hermes/config.yaml#custom_providers[",
            "hermes/",
        )
    )


def _openclaw_owns_structured_pair(pair) -> bool:
    group = str(getattr(pair, "group", "") or "").strip()
    return group.startswith(_OPENCLAW_PROVIDER_GROUP_PREFIX) or group.startswith("openclaw/")


def _codex_provider_semantic_field_identity(field_obj) -> tuple[str, str, str]:
    source = _runtime_field_source(field_obj)
    if source != ".codex/config.toml":
        return ("", "", "")
    field = str(getattr(field_obj, "field", "") or "").strip()
    if field != "base_url":
        return ("", "", "")
    source_detail = _runtime_field_source_detail(field_obj)
    if source_detail and (
        not source_detail.startswith("toml:model_providers.")
        or not source_detail.endswith(".base_url")
    ):
        return ("", "", "")
    value = _runtime_field_original_value(field_obj)
    if not value:
        return ("", "", "")
    return (source, field, value)


def _hermes_provider_semantic_field_identity(field_obj) -> tuple[str, str, str]:
    source = _runtime_field_source(field_obj)
    if source != ".hermes/config.yaml":
        return ("", "", "")
    field = str(getattr(field_obj, "field", "") or "").strip()
    if not field:
        return ("", "", "")
    semantic_field = field.rsplit(".", 1)[-1]
    if semantic_field not in {"api_key", "base_url"}:
        return ("", "", "")
    value = _runtime_field_original_value(field_obj)
    if not value:
        return ("", "", "")
    return (source, semantic_field, value)


def _openclaw_provider_semantic_field_identity(field_obj) -> tuple[str, str, str]:
    source = _runtime_field_source(field_obj)
    if source != ".openclaw/openclaw.json":
        return ("", "", "")
    field = str(getattr(field_obj, "field", "") or "").strip()
    parts = field.split(".")
    semantic_field = ""
    if len(parts) == 4 and parts[:2] == ["models", "providers"]:
        semantic_field = parts[3]
    elif "." not in field:
        semantic_field = field
    if semantic_field not in {"apiKey", "baseUrl"}:
        return ("", "", "")
    value = _runtime_field_original_value(field_obj)
    if not value:
        return ("", "", "")
    return (source, semantic_field, value)


_RUNTIME_ADAPTERS = (
    RuntimeAdapter(
        runtime_id="codex",
        descriptors=_codex_descriptors,
        target_factory=_codex_target_factory,
        url_proxy_runtime_factory=_codex_url_proxy_runtime_factory,
        review_consistency_hook=_make_review_consistency_hook("packaging.configure.runtimes.codex.review_consistency"),
        semantic_field_identity_hook=_codex_provider_semantic_field_identity,
    ),
    RuntimeAdapter(
        runtime_id="claude_code",
        descriptors=_claude_code_descriptors,
        target_factory=_claude_code_target_factory,
        url_proxy_runtime_factory=_claude_code_url_proxy_runtime_factory,
        env_preprocess_hook=_claude_code_preprocess_env_sources,
        owns_structured_pair=_claude_code_owns_structured_pair,
        review_consistency_hook=_make_review_consistency_hook("packaging.configure.runtimes.claude_code.review_consistency"),
    ),
    RuntimeAdapter(
        runtime_id="openclaw",
        descriptors=_openclaw_descriptors,
        target_factory=_openclaw_target_factory,
        url_proxy_runtime_factory=_openclaw_url_proxy_runtime_factory,
        env_preprocess_hook=_openclaw_preprocess_env_sources,
        owns_structured_pair=_openclaw_owns_structured_pair,
        review_consistency_hook=_make_review_consistency_hook("packaging.configure.runtimes.openclaw.review_consistency"),
        semantic_field_identity_hook=_openclaw_provider_semantic_field_identity,
    ),
    RuntimeAdapter(
        runtime_id="hermes",
        descriptors=_hermes_descriptors,
        target_factory=_hermes_target_factory,
        url_proxy_runtime_factory=_hermes_url_proxy_runtime_factory,
        env_preprocess_hook=_hermes_preprocess_env_sources,
        owns_structured_pair=_hermes_owns_structured_pair,
        review_consistency_hook=_make_review_consistency_hook("packaging.configure.runtimes.hermes.review_consistency"),
        semantic_field_identity_hook=_hermes_provider_semantic_field_identity,
    ),
)


@lru_cache(maxsize=1)
def list_runtime_adapters() -> tuple[RuntimeAdapter, ...]:
    return _RUNTIME_ADAPTERS


@lru_cache(maxsize=1)
def _runtime_adapters_by_id() -> dict[str, RuntimeAdapter]:
    return {adapter.runtime_id: adapter for adapter in list_runtime_adapters()}


@lru_cache(maxsize=1)
def _runtime_adapters_by_target_id() -> dict[str, RuntimeAdapter]:
    adapters: dict[str, RuntimeAdapter] = {}
    for adapter in list_runtime_adapters():
        for descriptor in adapter.descriptors():
            adapters[descriptor.target_id] = adapter
    return adapters


def get_runtime_adapter(runtime_id: str) -> RuntimeAdapter:
    normalized = str(runtime_id or "").strip()
    try:
        return _runtime_adapters_by_id()[normalized]
    except KeyError as exc:
        raise ValueError(f"unknown runtime adapter: {runtime_id}") from exc


def get_runtime_adapter_for_target(target_id: str) -> RuntimeAdapter:
    normalized = str(target_id or "").strip()
    try:
        return _runtime_adapters_by_target_id()[normalized]
    except KeyError as exc:
        raise ValueError(f"unknown runtime adapter target: {target_id}") from exc


__all__ = [
    "get_runtime_adapter",
    "get_runtime_adapter_for_target",
    "list_runtime_adapters",
]
