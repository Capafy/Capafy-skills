from __future__ import annotations

from pathlib import Path
from typing import Any

from packaging.configure.runtimes.codex.auth import CODEX_AUTH_PROVIDER_NAME
from packaging.configure.runtimes.codex.config_state import CONFIG_RELPATH
from packaging.configure.url_proxy.review_consistency import (
    PlaceholderReviewRequirement,
    append_placeholder_requirement_if_managed,
    load_toml_config_for_review,
    validate_placeholder_review_requirements,
)


PROVIDER_GROUP_PREFIX = f"{CONFIG_RELPATH}#model_providers."
REVIEWED_BASE_URL_FIELDS = frozenset({"base_url", "OPENAI_BASE_URL", "openai_base_url"})


def validate_review_consistency(
    staging_root: Path,
    *,
    reviewed_scan: dict[str, Any],
) -> None:
    payload = load_toml_config_for_review(staging_root, CONFIG_RELPATH, label="Codex config")
    if payload is None:
        return

    provider_name = str(payload.get("model_provider", "") or "").strip() or CODEX_AUTH_PROVIDER_NAME
    providers = payload.get("model_providers")
    provider = providers.get(provider_name) if isinstance(providers, dict) else None
    if not isinstance(provider, dict):
        return
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
    if not requirements:
        return
    validate_placeholder_review_requirements(
        reviewed_scan,
        requirements=requirements,
        error_prefix="Codex provider placeholders are missing url_proxy review entries",
    )


__all__ = ["validate_review_consistency"]
