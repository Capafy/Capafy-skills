from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from packaging._shared.common.url_values import normalize_http_url_candidate
from packaging._shared.llm.official_providers import (
    OfficialProviderSpec,
    find_official_provider_by_base_url,
    find_official_provider_by_marker,
)
from packaging.configure.candidate import Candidate
from packaging.configure.contracts import FieldLocation, SourceKind
from packaging.configure.env_values import (
    env_reference_name,
    resolve_env_reference_or_value,
    usable_env_value,
)
from packaging.configure.runtimes.hermes.api_modes import platform_api_format_from_block
from packaging.configure.runtimes.hermes.provider_blocks import (
    HermesProviderBlock,
    block_field_path,
    block_model_field,
    iter_hermes_provider_blocks,
)
from packaging.configure.runtimes.hermes.provider_refs import (
    custom_provider_name_map,
    provider_block_has_inline_credentials,
    referenced_custom_provider_group,
)
from packaging.configure.staging.env_preprocess import RuntimeEnvContext


CONFIG_REL = ".hermes/config.yaml"
HERMES_DOTENV_RELPATHS = (".hermes/.env", ".env")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_ENV_KEY = "OPENROUTER_API_KEY"
_HERMES_PROVIDER_ALIASES = {
    "minimax-cn": "minimax",
}


def scan_hermes_provider_candidates(
    config: dict[str, Any],
    *,
    staging_root: Path,
    env_context: RuntimeEnvContext,
    process_env: Optional[dict[str, str]] = None,
) -> list[Candidate]:
    candidates: list[Candidate] = []
    env_names = _all_provider_env_names(config)
    env = env_context.env_for_names(env_names)
    if process_env:
        env.update({key: value for key, value in process_env.items() if isinstance(value, str)})
    dotenv_values = env_context.staged_dotenv_values(
        staging_root,
        relpaths=HERMES_DOTENV_RELPATHS,
        names=env_names,
    )
    env.update({key: value for key, value in dotenv_values.items() if isinstance(value, str)})

    custom_provider_groups = custom_provider_name_map(config)
    for provider_block in iter_hermes_provider_blocks(config):
        referenced_group = referenced_custom_provider_group(provider_block, custom_provider_groups)
        if referenced_group:
            if provider_block_has_inline_credentials(provider_block):
                raise ValueError(
                    "Hermes provider block "
                    f"{provider_block.group_path} references {referenced_group} "
                    "but also defines inline credentials; use either a pure custom provider reference "
                    "or a standalone inline provider block."
                )
            continue
        candidates.extend(_scan_block(provider_block, env=env))
    return candidates


def _scan_block(provider_block: HermesProviderBlock, *, env: dict[str, str]) -> list[Candidate]:
    block = provider_block.block
    spec = resolve_hermes_official_spec(block)
    service = _block_service(provider_block, spec)
    provider_name = spec.provider_name if spec else service
    api_format = _block_api_format(block, spec)
    base_url = _block_base_url(block, spec)
    model_field_name = block_model_field(provider_block)
    model = str(block.get(model_field_name, "") or "").strip()
    raw_key = block.get("api_key", "") or block.get("key_env", "")
    env_name = env_reference_name(raw_key)
    value = resolve_env_reference_or_value(raw_key, env)
    source_kind = SourceKind.FILE
    if not value:
        for name in hermes_default_env_names(block, spec):
            value = usable_env_value(env.get(name, ""))
            if value:
                env_name = name
                break

    if not value and env_name:
        value = usable_env_value(env.get(env_name, ""))
    if not value:
        value = usable_env_value(raw_key)

    result: list[Candidate] = []
    emit_primary_key = bool(
        value
        or env_name
        or spec is not None
        or normalize_http_url_candidate(base_url)
    )
    if emit_primary_key:
        result.append(Candidate(
            role="api_key",
            field=".".join(block_field_path(provider_block, "api_key")),
            value=value,
            source_kind=source_kind,
            source_relpath=CONFIG_REL,
            location=FieldLocation(fmt="yaml", key_path=block_field_path(provider_block, "api_key")),
            extra=_extra(
                provider_block,
                provider_name=provider_name,
                service=service,
                model=model,
                model_field=model_field_name,
                base_url=base_url,
                api_format=api_format,
                env_name=env_name,
                placeholder_provider=not bool(value),
            ),
        ))

    if base_url:
        result.append(Candidate(
            role="base_url",
            field=".".join(block_field_path(provider_block, "base_url")),
            value=base_url,
            source_kind=SourceKind.FILE,
            source_relpath=CONFIG_REL,
            location=FieldLocation(fmt="yaml", key_path=block_field_path(provider_block, "base_url")),
            extra=_extra(
                provider_block,
                provider_name=provider_name,
                service=service,
                model=model,
                model_field=model_field_name,
                base_url=base_url,
                api_format=api_format,
                env_name=env_name,
            ),
        ))

    if model:
        result.append(Candidate(
            role="url_proxy_group",
            field=".".join(block_field_path(provider_block, model_field_name)),
            value=model,
            source_kind=SourceKind.FILE,
            source_relpath=CONFIG_REL,
            location=FieldLocation(fmt="yaml", key_path=block_field_path(provider_block, model_field_name)),
            extra=_extra(
                provider_block,
                provider_name=provider_name,
                service=service,
                model=model,
                model_field=model_field_name,
                base_url=base_url,
                api_format=api_format,
                env_name=env_name,
            ),
        ))

    return result


def _extra(
    provider_block: HermesProviderBlock,
    *,
    provider_name: str,
    service: str,
    model: str,
    model_field: str,
    base_url: str,
    api_format: str,
    env_name: str,
    placeholder_provider: bool = False,
) -> dict[str, object]:
    return {
        "provider_name": provider_name,
        "service": service,
        "group_path": provider_block.group_path,
        "key_path": provider_block.key_path,
        "model": model,
        "model_field": model_field,
        "base_url": base_url,
        "api_format": api_format,
        "env_name": env_name,
        "placeholder_provider": placeholder_provider,
        "is_custom": provider_block.is_custom,
    }


def resolve_hermes_official_spec(block: dict[str, Any]) -> Optional[OfficialProviderSpec]:
    for field in ("provider", "name"):
        marker = _canonical_provider_marker(str(block.get(field, "") or "").strip())
        spec = find_official_provider_by_marker(marker)
        if spec is not None:
            return spec
    return find_official_provider_by_base_url(str(block.get("base_url", "") or ""))


def _block_service(provider_block: HermesProviderBlock, spec: Optional[OfficialProviderSpec]) -> str:
    if spec is not None:
        return spec.service
    block = provider_block.block
    provider = _canonical_provider_marker(str(block.get("provider", "") or "").strip()).lower()
    if provider == "openrouter":
        return "OpenRouter"
    for field in ("name", "provider"):
        value = str(block.get(field, "") or "").strip()
        if value:
            return value
    return provider_block.group_path


def _block_api_format(block: dict[str, Any], spec: Optional[OfficialProviderSpec]) -> str:
    return platform_api_format_from_block(block, spec)


def _block_base_url(block: dict[str, Any], spec: Optional[OfficialProviderSpec]) -> str:
    value = normalize_http_url_candidate(str(block.get("base_url", "") or ""))
    if value:
        return value
    if spec is not None:
        return spec.base_url
    provider = _canonical_provider_marker(str(block.get("provider", "") or "").strip()).lower()
    if provider == "openrouter":
        return OPENROUTER_BASE_URL
    return ""


def hermes_default_env_names(block: dict[str, Any], spec: Optional[OfficialProviderSpec]) -> tuple[str, ...]:
    if spec is not None:
        return spec.exact_env_keys
    provider = _canonical_provider_marker(str(block.get("provider", "") or "").strip()).lower()
    if provider == "openrouter":
        return (OPENROUTER_ENV_KEY,)
    return ()


def _all_provider_env_names(config: dict[str, Any]) -> frozenset[str]:
    names = {
        OPENROUTER_ENV_KEY,
    }
    from packaging._shared.llm.official_providers import ALL_OFFICIAL_PROVIDER_SPECS

    for spec in ALL_OFFICIAL_PROVIDER_SPECS:
        names.update(spec.exact_env_keys)
    for provider_block in iter_hermes_provider_blocks(config):
        env_name = env_reference_name(provider_block.block.get("api_key", "") or provider_block.block.get("key_env", ""))
        if env_name:
            names.add(env_name)
    return frozenset(names)


def _canonical_provider_marker(value: str) -> str:
    normalized = str(value or "").strip().lower()
    return _HERMES_PROVIDER_ALIASES.get(normalized, normalized)


__all__ = [
    "CONFIG_REL",
    "HERMES_DOTENV_RELPATHS",
    "hermes_default_env_names",
    "resolve_hermes_official_spec",
    "scan_hermes_provider_candidates",
]
