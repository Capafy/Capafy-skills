from __future__ import annotations

from typing import Any
from typing import Optional

from packaging._shared.llm.official_providers import find_official_provider_by_marker
from packaging.configure.runtimes.hermes.provider_blocks import HermesProviderBlock


def find_custom_provider(custom_providers: list[Any], name: object) -> Optional[dict[str, Any]]:
    normalized = _normalize_provider_name(name)
    if not normalized:
        return None
    for provider in custom_providers:
        if not isinstance(provider, dict):
            continue
        if _normalize_provider_name(provider.get("name")) == normalized:
            return provider
    return None


def custom_provider_name_map(config: dict[str, Any]) -> dict[str, str]:
    providers = config.get("custom_providers")
    if not isinstance(providers, list):
        return {}
    result: dict[str, str] = {}
    for index, item in enumerate(providers):
        if not isinstance(item, dict):
            continue
        name = _normalize_provider_name(item.get("name"))
        if not name:
            continue
        result.setdefault(name, f"custom_providers[{index}]")
    return result


def referenced_custom_provider_group(
    provider_block: HermesProviderBlock,
    custom_provider_groups: dict[str, str],
) -> str:
    if provider_block.is_custom:
        return ""
    raw_provider = str(provider_block.block.get("provider", "") or "").strip()
    if not raw_provider:
        return ""
    if raw_provider.lower().startswith("custom:"):
        name = _normalize_provider_name(raw_provider.split(":", 1)[1])
        return custom_provider_groups.get(name, "")
    name = _normalize_provider_name(raw_provider)
    if _is_builtin_provider_name(name):
        return ""
    return custom_provider_groups.get(name, "")


def provider_block_has_inline_credentials(provider_block: HermesProviderBlock) -> bool:
    block = provider_block.block
    for field in ("api_key", "key_env", "base_url"):
        value = block.get(field)
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, list) and any(str(item or "").strip() for item in value):
            return True
    return False


def _normalize_provider_name(value: object) -> str:
    return str(value or "").strip().lower()


def _is_builtin_provider_name(value: str) -> bool:
    if value == "openrouter":
        return True
    return find_official_provider_by_marker(value) is not None


__all__ = [
    "custom_provider_name_map",
    "find_custom_provider",
    "provider_block_has_inline_credentials",
    "referenced_custom_provider_group",
]
