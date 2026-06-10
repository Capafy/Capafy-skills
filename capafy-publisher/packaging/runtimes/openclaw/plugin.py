from __future__ import annotations

from importlib import import_module

from packaging._shared.runtimes.contracts import (
    OPENCLAW_LEGACY_TARGET,
    OPENCLAW_MODERN_TARGET,
    RuntimePlugin,
    TargetDescriptor,
)


_OPENCLAW_PROVIDER_GROUP_PREFIX = ".openclaw/openclaw.json#models.providers."


def descriptors() -> tuple[TargetDescriptor, ...]:
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


def build_target(descriptor: TargetDescriptor, profile: dict):
    openclaw_target = import_module("packaging.runtimes.openclaw.target")
    if descriptor.runtime_variant == "legacy":
        return openclaw_target.LEGACY_TARGET
    if descriptor.runtime_variant == "modern":
        return openclaw_target.MODERN_TARGET
    raise ValueError(f"{descriptor.target_id} is missing openclaw runtime_variant, so the target cannot be built")


def build_url_proxy_runtime():
    OpenClawRuntime = import_module("packaging.configure.runtimes.openclaw").OpenClawRuntime
    return OpenClawRuntime()


def preprocess_env_sources(staging_root, *, env_context):
    resolve_openclaw_staged_env_templates = import_module(
        "packaging.configure.runtimes.openclaw.provider_rewrite"
    ).resolve_openclaw_staged_env_templates
    return frozenset(resolve_openclaw_staged_env_templates(staging_root, env_context=env_context))


def owns_structured_pair(pair) -> bool:
    group = str(getattr(pair, "group", "") or "").strip()
    return group.startswith(_OPENCLAW_PROVIDER_GROUP_PREFIX) or group.startswith("openclaw/")


def validate_review_consistency(staging_root, *, reviewed_scan):
    validate = import_module(
        "packaging.configure.runtimes.openclaw.review_consistency"
    ).validate_review_consistency
    validate(staging_root, reviewed_scan=reviewed_scan)


def _field_source(field_obj) -> str:
    source_identity = getattr(field_obj, "source_identity", None)
    if callable(source_identity):
        return str(source_identity() or "").strip()
    return str(getattr(field_obj, "source_relpath", "") or "").strip()


def openclaw_provider_semantic_field_identity(field_obj) -> tuple[str, str, str]:
    source = _field_source(field_obj)
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
    value = str(getattr(field_obj, "original_value", "") or "").strip()
    if not value:
        return ("", "", "")
    return (source, semantic_field, value)


PLUGIN = RuntimePlugin(
    runtime_id="openclaw",
    descriptors=descriptors,
    target_factory=build_target,
    url_proxy_runtime_factory=build_url_proxy_runtime,
    env_preprocess_hook=preprocess_env_sources,
    owns_structured_pair=owns_structured_pair,
    review_consistency_hook=validate_review_consistency,
    semantic_field_identity_hook=openclaw_provider_semantic_field_identity,
)


__all__ = ["PLUGIN"]
