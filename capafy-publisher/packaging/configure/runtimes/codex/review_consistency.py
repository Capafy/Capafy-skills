from __future__ import annotations

from pathlib import Path
from typing import Any

from packaging.configure.runtimes.codex.auth import CODEX_AUTH_PROVIDER_NAME
from packaging.configure.runtimes.codex.config_state import CONFIG_RELPATH
from packaging.configure.url_proxy.review_consistency import (
    PlaceholderReviewRequirement,
    append_placeholder_requirement_if_managed,
    toml_config_review_loader,
    validate_config_placeholder_review_requirements,
)


PROVIDER_GROUP_PREFIX = f"{CONFIG_RELPATH}#model_providers."
REVIEWED_BASE_URL_FIELDS = frozenset({"base_url", "OPENAI_BASE_URL", "openai_base_url"})


def validate_review_consistency(
    staging_root: Path,
    *,
    reviewed_scan: dict[str, Any],
) -> None:
    validate_config_placeholder_review_requirements(
        staging_root,
        reviewed_scan=reviewed_scan,
        relpath=CONFIG_RELPATH,
        loader=toml_config_review_loader("Codex config"),
        requirement_builder=_build_requirements,
        error_prefix="Codex provider placeholders are missing url_proxy review entries",
    )


def _build_requirements(payload: dict[str, Any]) -> list[PlaceholderReviewRequirement]:
    provider_name = str(payload.get("model_provider", "") or "").strip() or CODEX_AUTH_PROVIDER_NAME
    providers = payload.get("model_providers")
    provider = providers.get(provider_name) if isinstance(providers, dict) else None
    if not isinstance(provider, dict):
        return []
    group = f"{PROVIDER_GROUP_PREFIX}{provider_name}"
    requirements: list[PlaceholderReviewRequirement] = []
    append_placeholder_requirement_if_managed(
        requirements,
        value=provider.get("base_url"),
        label=f"{provider_name}.base_url",
        source=CONFIG_RELPATH,
        side_name="url",
        fields=REVIEWED_BASE_URL_FIELDS,
        group=group,
    )
    return requirements


__all__ = ["validate_review_consistency"]
