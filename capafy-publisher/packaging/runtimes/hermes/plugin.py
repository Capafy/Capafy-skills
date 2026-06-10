from __future__ import annotations

from importlib import import_module

from packaging._shared.runtimes.contracts import RuntimePlugin, TargetDescriptor


_HERMES_RUNTIME_GENERATION = "hermes_v1"


def descriptors() -> tuple[TargetDescriptor, ...]:
    return (
        TargetDescriptor(
            target_id="hermes",
            canonical_name="hermes",
            profile_env_id="hermes",
            runtime_generation=_HERMES_RUNTIME_GENERATION,
        ),
    )


def build_target(descriptor: TargetDescriptor, profile: dict):
    HermesTarget = import_module("packaging.runtimes.hermes.target").HermesTarget
    return HermesTarget(profile)


def build_url_proxy_runtime():
    HermesRuntime = import_module("packaging.configure.runtimes.hermes.url_proxy").HermesRuntime
    return HermesRuntime()


def preprocess_env_sources(staging_root, *, env_context):
    resolve_hermes_staged_env_templates = import_module(
        "packaging.configure.runtimes.hermes.provider_rewrite"
    ).resolve_hermes_staged_env_templates
    return frozenset(resolve_hermes_staged_env_templates(staging_root, env_context=env_context))


def owns_structured_pair(pair) -> bool:
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


def validate_review_consistency(staging_root, *, reviewed_scan):
    validate = import_module(
        "packaging.configure.runtimes.hermes.review_consistency"
    ).validate_review_consistency
    validate(staging_root, reviewed_scan=reviewed_scan)


def _field_source(field_obj) -> str:
    source_identity = getattr(field_obj, "source_identity", None)
    if callable(source_identity):
        return str(source_identity() or "").strip()
    return str(getattr(field_obj, "source_relpath", "") or "").strip()


def hermes_provider_semantic_field_identity(field_obj) -> tuple[str, str, str]:
    source = _field_source(field_obj)
    if source != ".hermes/config.yaml":
        return ("", "", "")
    field = str(getattr(field_obj, "field", "") or "").strip()
    if not field:
        return ("", "", "")
    semantic_field = field.rsplit(".", 1)[-1]
    if semantic_field not in {"api_key", "base_url"}:
        return ("", "", "")
    value = str(getattr(field_obj, "original_value", "") or "").strip()
    if not value:
        return ("", "", "")
    return (source, semantic_field, value)


PLUGIN = RuntimePlugin(
    runtime_id="hermes",
    descriptors=descriptors,
    target_factory=build_target,
    url_proxy_runtime_factory=build_url_proxy_runtime,
    env_preprocess_hook=preprocess_env_sources,
    owns_structured_pair=owns_structured_pair,
    review_consistency_hook=validate_review_consistency,
    semantic_field_identity_hook=hermes_provider_semantic_field_identity,
)


__all__ = ["PLUGIN"]
