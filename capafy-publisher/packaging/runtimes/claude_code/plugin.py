from __future__ import annotations

from importlib import import_module

from packaging._shared.runtimes.contracts import RuntimePlugin, TargetDescriptor


def descriptors() -> tuple[TargetDescriptor, ...]:
    return (
        TargetDescriptor(
            target_id="claude_code",
            canonical_name="claude_code",
            profile_env_id="claude_code",
        ),
    )


def build_target(descriptor: TargetDescriptor, profile: dict):
    ClaudeCodeTarget = import_module("packaging.runtimes.claude_code.target").ClaudeCodeTarget
    return ClaudeCodeTarget(profile)


def build_url_proxy_runtime():
    ClaudeCodeRuntime = import_module("packaging.configure.runtimes.claude_code.url_proxy").ClaudeCodeRuntime
    return ClaudeCodeRuntime()


def preprocess_env_sources(staging_root, *, env_context):
    settings_json = import_module("packaging.configure.runtimes.claude_code.settings_json")
    settings_json.prune_settings_proxy_env_sources(staging_root)
    return settings_json.preprocess_settings_model_env(staging_root, env_context=env_context)


def owns_structured_pair(pair) -> bool:
    SETTINGS_SCAN_RELPATHS = import_module(
        "packaging.configure.runtimes.claude_code.url_proxy_candidates"
    ).SETTINGS_SCAN_RELPATHS
    key_source = str(getattr(pair.key, "source_relpath", "") or "").strip()
    url_source = str(getattr(pair.url, "source_relpath", "") or "").strip()
    return key_source in SETTINGS_SCAN_RELPATHS or url_source in SETTINGS_SCAN_RELPATHS


def validate_review_consistency(staging_root, *, reviewed_scan):
    validate = import_module(
        "packaging.configure.runtimes.claude_code.review_consistency"
    ).validate_review_consistency
    validate(staging_root, reviewed_scan=reviewed_scan)


PLUGIN = RuntimePlugin(
    runtime_id="claude_code",
    descriptors=descriptors,
    target_factory=build_target,
    url_proxy_runtime_factory=build_url_proxy_runtime,
    env_preprocess_hook=preprocess_env_sources,
    owns_structured_pair=owns_structured_pair,
    review_consistency_hook=validate_review_consistency,
)


__all__ = ["PLUGIN"]
