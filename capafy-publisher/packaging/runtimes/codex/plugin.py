from __future__ import annotations

from importlib import import_module

from packaging._shared.runtimes.contracts import RuntimePlugin, TargetDescriptor


_CODEX_RUNTIME_GENERATION = "codex_standalone"


def descriptors() -> tuple[TargetDescriptor, ...]:
    return (
        TargetDescriptor(
            target_id="codex",
            canonical_name="codex",
            profile_env_id="codex",
            runtime_generation=_CODEX_RUNTIME_GENERATION,
        ),
    )


def build_target(descriptor: TargetDescriptor, profile: dict):
    CodexTarget = import_module("packaging.runtimes.codex.target").CodexTarget
    return CodexTarget(profile)


def build_url_proxy_runtime():
    CodexRuntime = import_module("packaging.configure.runtimes.codex.url_proxy").CodexRuntime
    return CodexRuntime()


def validate_review_consistency(staging_root, *, reviewed_scan):
    validate = import_module(
        "packaging.configure.runtimes.codex.review_consistency"
    ).validate_review_consistency
    validate(staging_root, reviewed_scan=reviewed_scan)


def _field_source(field_obj) -> str:
    source_identity = getattr(field_obj, "source_identity", None)
    if callable(source_identity):
        return str(source_identity() or "").strip()
    return str(getattr(field_obj, "source_relpath", "") or "").strip()


def _field_source_detail(field_obj) -> str:
    source_detail_identity = getattr(field_obj, "source_detail_identity", None)
    if callable(source_detail_identity):
        return str(source_detail_identity() or "").strip()
    return ""


def codex_provider_semantic_field_identity(field_obj) -> tuple[str, str, str]:
    source = _field_source(field_obj)
    if source != ".codex/config.toml":
        return ("", "", "")
    field = str(getattr(field_obj, "field", "") or "").strip()
    if field != "base_url":
        return ("", "", "")
    source_detail = _field_source_detail(field_obj)
    if source_detail and (
        not source_detail.startswith("toml:model_providers.")
        or not source_detail.endswith(".base_url")
    ):
        return ("", "", "")
    value = str(getattr(field_obj, "original_value", "") or "").strip()
    if not value:
        return ("", "", "")
    return (source, field, value)


PLUGIN = RuntimePlugin(
    runtime_id="codex",
    descriptors=descriptors,
    target_factory=build_target,
    url_proxy_runtime_factory=build_url_proxy_runtime,
    review_consistency_hook=validate_review_consistency,
    semantic_field_identity_hook=codex_provider_semantic_field_identity,
)


__all__ = ["PLUGIN"]
