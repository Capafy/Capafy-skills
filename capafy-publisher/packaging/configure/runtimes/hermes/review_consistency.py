from __future__ import annotations

from pathlib import Path
from typing import Any

from packaging.configure.runtimes.hermes.provider_blocks import iter_hermes_provider_blocks
from packaging.configure.url_proxy.review_consistency import (
    PlaceholderReviewRequirement,
    append_key_url_placeholder_requirements,
    validate_config_placeholder_review_requirements,
    yaml_config_review_loader,
)


CONFIG_REL = ".hermes/config.yaml"


def validate_review_consistency(
    staging_root: Path,
    *,
    reviewed_scan: dict[str, Any],
) -> None:
    validate_config_placeholder_review_requirements(
        staging_root,
        reviewed_scan=reviewed_scan,
        relpath=CONFIG_REL,
        loader=yaml_config_review_loader("Hermes config.yaml"),
        requirement_builder=_build_requirements,
        error_prefix="Hermes provider placeholders are missing url_proxy review entries",
    )


def _build_requirements(payload: dict[str, Any]) -> list[PlaceholderReviewRequirement]:
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
    return requirements


__all__ = ["validate_review_consistency"]
