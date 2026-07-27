from __future__ import annotations

from packaging._shared.llm.api_formats import PLATFORM_API_FORMAT_OPENAI_RESPONSES
from packaging._shared.llm.official_providers import (
    OfficialProviderSpec,
    find_official_provider_by_base_url,
    find_official_provider_by_marker,
)


def validate_codex_provider_capability(
    *,
    api_format: object,
    provider_name: object = "",
    base_url: object = "",
) -> None:
    normalized_api_format = str(api_format or "").strip()
    if normalized_api_format != PLATFORM_API_FORMAT_OPENAI_RESPONSES:
        raise ValueError(
            "Codex only supports api_format=\"openai-responses\"; "
            f'got "{normalized_api_format or "<empty>"}"'
        )

    normalized_provider_name = str(provider_name or "").strip()
    provider_spec = find_official_provider_by_marker(normalized_provider_name)
    if provider_spec is not None:
        _require_responses_official_provider(provider_spec, matched_by="provider_name")

    normalized_base_url = str(base_url or "").strip()
    url_spec = find_official_provider_by_base_url(normalized_base_url)
    if url_spec is not None:
        _require_responses_official_provider(url_spec, matched_by="base_url")


def _require_responses_official_provider(
    spec: OfficialProviderSpec,
    *,
    matched_by: str,
) -> None:
    if spec.api == PLATFORM_API_FORMAT_OPENAI_RESPONSES:
        return
    raise ValueError(
        f'Codex does not support official provider "{spec.provider_name}" matched by {matched_by}; '
        f'its api_format is "{spec.api}", but Codex requires "{PLATFORM_API_FORMAT_OPENAI_RESPONSES}"'
    )


__all__ = [
    "validate_codex_provider_capability",
]
