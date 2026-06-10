from __future__ import annotations

from pathlib import Path
from typing import Any

from packaging.configure.runtimes.hermes.provider_blocks import iter_hermes_provider_blocks
from packaging.configure.url_proxy.review_consistency import (
    PlaceholderReviewRequirement,
    append_key_url_placeholder_requirements,
    load_yaml_config_for_review,
    validate_placeholder_review_requirements,
)


CONFIG_REL = ".hermes/config.yaml"


def validate_review_consistency(
    staging_root: Path,
    *,
    reviewed_scan: dict[str, Any],
) -> None:
    payload = load_yaml_config_for_review(staging_root, CONFIG_REL)
    if payload is None:
        return

    requirements: list[PlaceholderReviewRequirement] = []
    for provider_block in iter_hermes_provider_blocks(payload):
        group_path = provider_block.group_path
        group = f"{CONFIG_REL}#{group_path}"
        block = provider_block.block
        append_key_url_placeholder_requirements(
            requirements,
            source=CONFIG_REL,
            group=group,
            key_value=block.get("api_key"),
            key_label=f"{group_path}.api_key",
            key_field=f"{group_path}.api_key",
            url_value=block.get("base_url"),
            url_label=f"{group_path}.base_url",
            url_field=f"{group_path}.base_url",
        )
    validate_placeholder_review_requirements(
        reviewed_scan,
        requirements=requirements,
        error_prefix="Hermes provider placeholders are missing url_proxy review entries",
    )


__all__ = ["validate_review_consistency"]
