from __future__ import annotations

import re
from typing import Any, Optional

from packaging._shared.common.url_values import normalize_http_url_candidate
from packaging._shared.llm.official_providers import OfficialProviderSpec, find_official_provider_by_marker
from packaging.configure.runtimes.hermes.api_modes import hermes_api_mode_from_block
from packaging.configure.runtimes.hermes.provider_blocks import (
    HermesProviderBlock,
    block_model_field,
    iter_hermes_provider_blocks,
)
from packaging.configure.runtimes.hermes.provider_refs import (
    custom_provider_name_map,
    find_custom_provider,
    provider_block_has_inline_credentials,
    referenced_custom_provider_group,
)
from packaging.configure.runtimes.hermes.provider_scan import (
    resolve_hermes_official_spec,
)
from packaging.configure.sensitive.literals import looks_like_platform_managed_placeholder_value


_PROVIDER_BLOCK_OWNED_FIELDS = {
    "api",
    "api_format",
    "api_key",
    "api_mode",
    "base_url",
    "default_model",
    "key_env",
}


def normalize_hermes_provider_blocks(config: dict[str, Any]) -> bool:
    custom_providers = config.get("custom_providers")
    if custom_providers is None:
        custom_providers = []
    elif not isinstance(custom_providers, list):
        return False

    changed = False
    custom_groups = custom_provider_name_map(config)
    assigned_names = {
        _normalize_name(item.get("name"))
        for item in custom_providers
        if isinstance(item, dict)
    }
    generated_by_identity: dict[tuple[str, str], str] = {}
    for index, item in enumerate(custom_providers):
        if not isinstance(item, dict):
            continue
        identity = _provider_identity(item)
        name = str(item.get("name", "") or "").strip()
        if identity and name:
            generated_by_identity.setdefault(identity, name)
        if name:
            custom_groups.setdefault(_normalize_name(name), f"custom_providers[{index}]")

    for provider_block in list(iter_hermes_provider_blocks(config)):
        changed = _drop_unsupported_credential_pool(provider_block) or changed
        if provider_block.is_custom:
            continue
        referenced_group = referenced_custom_provider_group(provider_block, custom_groups)
        if referenced_group:
            if provider_block_has_inline_credentials(provider_block):
                continue
            changed = _normalize_reference_spelling(provider_block) or changed
            continue

        normalized = _normalize_provider_block(
            provider_block,
            config=config,
            custom_providers=custom_providers,
            assigned_names=assigned_names,
            generated_by_identity=generated_by_identity,
        )
        if normalized:
            changed = True
            custom_groups = custom_provider_name_map(config)

    return changed


def _normalize_provider_block(
    provider_block: HermesProviderBlock,
    *,
    config: dict[str, Any],
    custom_providers: list[Any],
    assigned_names: set[str],
    generated_by_identity: dict[tuple[str, str], str],
) -> bool:
    block = provider_block.block
    spec = resolve_hermes_official_spec(block)
    base_url = _block_base_url(block, spec)
    inline_credentials = provider_block_has_inline_credentials(provider_block)
    if spec is None and not inline_credentials:
        return False
    if not base_url:
        return False

    identity = _normalization_identity(provider_block, spec, base_url)
    provider_name = generated_by_identity.get(identity, "")
    if not provider_name:
        provider_name = _provider_name(provider_block, spec, custom_providers, assigned_names)
        generated_by_identity[identity] = provider_name

    provider = find_custom_provider(custom_providers, provider_name)
    if provider is None:
        if not isinstance(config.get("custom_providers"), list):
            config["custom_providers"] = custom_providers
        provider = {"name": provider_name}
        custom_providers.append(provider)

    changed = _merge_provider_definition(
        provider,
        source_block=block,
        provider_block=provider_block,
        provider_name=provider_name,
        spec=spec,
        base_url=base_url,
    )
    changed = _rewrite_block_as_reference(provider_block, provider_name) or changed
    return changed


def _merge_provider_definition(
    provider: dict[str, Any],
    *,
    source_block: dict[str, Any],
    provider_block: HermesProviderBlock,
    provider_name: str,
    spec: Optional[OfficialProviderSpec],
    base_url: str,
) -> bool:
    changed = False
    if provider.get("name") != provider_name:
        provider["name"] = provider_name
        changed = True

    changed = _set_if_missing(provider, "base_url", base_url) or changed

    raw_key = _first_non_empty(source_block.get("api_key")) or _first_non_empty(source_block.get("key_env"))
    changed = _set_if_missing(provider, "api_key", raw_key) or changed
    key_env = _first_non_empty(source_block.get("key_env"))
    if key_env:
        changed = _set_if_missing(provider, "key_env", key_env) or changed

    api_format = _api_format(source_block, spec)
    changed = _set_if_missing(provider, "api_mode", api_format) or changed

    model = _block_model(provider_block)
    changed = _set_if_missing(provider, "model", model) or changed

    return changed


def _rewrite_block_as_reference(provider_block: HermesProviderBlock, provider_name: str) -> bool:
    block = provider_block.block
    changed = False
    reference = f"custom:{provider_name}"
    if block.get("provider") != reference:
        block["provider"] = reference
        changed = True
    for field in _PROVIDER_BLOCK_OWNED_FIELDS:
        if field in block:
            block.pop(field, None)
            changed = True
    return changed


def _normalize_reference_spelling(provider_block: HermesProviderBlock) -> bool:
    provider = str(provider_block.block.get("provider", "") or "").strip()
    if not provider or provider.lower().startswith("custom:"):
        return False
    provider_block.block["provider"] = f"custom:{provider}"
    return True


def _provider_name(
    provider_block: HermesProviderBlock,
    spec: Optional[OfficialProviderSpec],
    custom_providers: list[Any],
    assigned_names: set[str],
) -> str:
    if spec is not None:
        candidate = spec.provider_name
    else:
        raw_provider = str(provider_block.block.get("provider", "") or "").strip()
        if raw_provider and raw_provider.lower() not in {"custom", "custom_provider"}:
            candidate = f"publisher_{_slug(raw_provider)}_custom"
        elif provider_block.group_path.startswith("providers."):
            candidate = _slug(provider_block.group_path.split(".", 1)[1])
        else:
            candidate = f"publisher_{_slug(provider_block.group_path)}_custom"

    normalized = _normalize_name(candidate)
    existing = find_custom_provider(custom_providers, candidate)
    if existing is None and normalized not in assigned_names:
        assigned_names.add(normalized)
        return candidate
    if isinstance(existing, dict) and _provider_payload_matches_name(existing, spec):
        assigned_names.add(normalized)
        return candidate

    suffix = 2
    while True:
        suffixed = f"{candidate}_{suffix}"
        normalized_suffixed = _normalize_name(suffixed)
        if find_custom_provider(custom_providers, suffixed) is None and normalized_suffixed not in assigned_names:
            assigned_names.add(normalized_suffixed)
            return suffixed
        suffix += 1


def _provider_payload_matches_name(provider: dict[str, Any], spec: Optional[OfficialProviderSpec]) -> bool:
    if spec is None:
        return False
    base_url = str(provider.get("base_url", "") or "").strip()
    if not base_url:
        return True
    if looks_like_platform_managed_placeholder_value(base_url):
        return True
    return normalize_http_url_candidate(base_url).rstrip("/") == spec.base_url.rstrip("/")


def _provider_identity(provider: dict[str, Any]) -> tuple[str, str]:
    name = _normalize_name(provider.get("name"))
    spec = find_official_provider_by_marker(_canonical_provider_marker(name))
    if spec is not None and name == spec.provider_name.lower():
        return ("official", spec.provider_name)
    base_url = normalize_http_url_candidate(str(provider.get("base_url", "") or ""))
    if name and base_url:
        return ("custom", name)
    return ("", "")


def _normalization_identity(
    provider_block: HermesProviderBlock,
    spec: Optional[OfficialProviderSpec],
    base_url: str,
) -> tuple[str, str]:
    if spec is not None:
        return ("official", spec.provider_name)
    return ("block", f"{provider_block.group_path}:{base_url}")


def _block_base_url(block: dict[str, Any], spec: Optional[OfficialProviderSpec]) -> str:
    value = normalize_http_url_candidate(str(block.get("base_url", "") or ""))
    if value:
        return value
    return spec.base_url if spec is not None else ""


def _api_format(block: dict[str, Any], spec: Optional[OfficialProviderSpec]) -> str:
    return hermes_api_mode_from_block(block, spec)


def _block_model(provider_block: HermesProviderBlock) -> str:
    return str(provider_block.block.get(block_model_field(provider_block), "") or "").strip()


def _set_if_missing(target: dict[str, Any], field: str, value: object) -> bool:
    if not _first_non_empty(value):
        return False
    existing = target.get(field)
    if _first_non_empty(existing):
        return False
    target[field] = value
    return True


def _first_non_empty(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return str(value or "").strip()


def _normalize_name(value: object) -> str:
    return str(value or "").strip().lower()


def _canonical_provider_marker(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "minimax-cn":
        return "minimax"
    return normalized


def _slug(value: object) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return normalized or "provider"


def _drop_unsupported_credential_pool(provider_block: HermesProviderBlock) -> bool:
    block = provider_block.block
    if "credential_pool" not in block:
        return False
    block.pop("credential_pool", None)
    return True


__all__ = ["normalize_hermes_provider_blocks"]
