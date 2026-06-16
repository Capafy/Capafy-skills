from __future__ import annotations

from pathlib import Path
from typing import Any

from packaging.configure.runtimes.claude_code.auth import (
    CLAUDE_AUTH_ENV_KEY,
    CLAUDE_AUTH_TOKEN_ENV_KEY,
    CLAUDE_BASE_URL_ENV_KEY,
)
from packaging.configure.url_proxy.review_consistency import (
    PlaceholderReviewRequirement,
    append_placeholder_requirement_if_managed,
    json_config_review_loader,
    validate_config_placeholder_review_requirements,
)


SETTINGS_REL = ".claude/settings.json"
MANAGED_ENV_FIELDS = frozenset({
    CLAUDE_AUTH_ENV_KEY,
    CLAUDE_AUTH_TOKEN_ENV_KEY,
    CLAUDE_BASE_URL_ENV_KEY,
})


def validate_review_consistency(
    staging_root: Path,
    *,
    reviewed_scan: dict[str, Any],
) -> None:
    validate_config_placeholder_review_requirements(
        staging_root,
        reviewed_scan=reviewed_scan,
        relpath=SETTINGS_REL,
        loader=json_config_review_loader("Claude settings"),
        requirement_builder=_build_requirements,
        error_prefix="Claude settings placeholders are missing url_proxy review entries",
    )


def _build_requirements(payload: dict[str, Any]) -> list[PlaceholderReviewRequirement]:
    env_payload = payload.get("env")
    if not isinstance(env_payload, dict):
        return []
    requirements: list[PlaceholderReviewRequirement] = []
    for field in sorted(MANAGED_ENV_FIELDS):
        append_placeholder_requirement_if_managed(
            requirements,
            value=env_payload.get(field),
            label=field,
            source=SETTINGS_REL,
            side_name="",
            fields=frozenset({field}),
        )
    return requirements


__all__ = ["validate_review_consistency"]
