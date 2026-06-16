from __future__ import annotations

from pathlib import Path
from typing import Any

from packaging.configure.runtimes.openclaw.provider_usage import (
    get_openclaw_providers as _get_providers,
)
from packaging.configure.runtimes.openclaw.provider_usage import selected_openclaw_provider_names
from packaging.configure.url_proxy.review_consistency import (
    PlaceholderReviewRequirement,
    append_key_url_placeholder_requirements,
    json_config_review_loader,
    validate_config_placeholder_review_requirements,
)


CONFIG_REL = ".openclaw/openclaw.json"
PROVIDER_GROUP_PREFIX = f"{CONFIG_REL}#models.providers."


def validate_review_consistency(
    staging_root: Path,
    *,
    reviewed_scan: dict[str, Any],
) -> None:
    validate_config_placeholder_review_requirements(
        staging_root,
        reviewed_scan=reviewed_scan,
        relpath=CONFIG_REL,
        loader=json_config_review_loader("OpenClaw config"),
        requirement_builder=_build_requirements,
        error_prefix="OpenClaw provider placeholders are missing url_proxy review entries",
    )


def _build_requirements(config: dict[str, Any]) -> list[PlaceholderReviewRequirement]:
    providers = _get_providers(config)
    if not providers:
        return []

    selected_providers = selected_openclaw_provider_names(config)
    requirements: list[PlaceholderReviewRequirement] = []
    for provider_name, provider in providers.items():
        if provider_name not in selected_providers or not isinstance(provider, dict):
            continue
        group = f"{PROVIDER_GROUP_PREFIX}{provider_name}"
        append_key_url_placeholder_requirements(
            requirements,
            source=CONFIG_REL,
            group=group,
            key_value=provider.get("apiKey"),
            key_label=f"{provider_name}.apiKey",
            key_field=f"models.providers.{provider_name}.apiKey",
            url_value=provider.get("baseUrl"),
            url_label=f"{provider_name}.baseUrl",
            url_field=f"models.providers.{provider_name}.baseUrl",
        )
    return requirements


__all__ = ["validate_review_consistency"]
