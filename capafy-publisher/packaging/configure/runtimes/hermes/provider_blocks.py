from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class HermesProviderBlock:
    group_path: str
    key_path: tuple[str, ...]
    block: dict[str, Any]
    is_custom: bool = False


def iter_hermes_provider_blocks(config: dict[str, Any]) -> Iterable[HermesProviderBlock]:
    model = config.get("model")
    if isinstance(model, dict):
        yield HermesProviderBlock("model", ("model",), model)

    auxiliary = config.get("auxiliary")
    if isinstance(auxiliary, dict):
        for name, block in auxiliary.items():
            if isinstance(block, dict):
                normalized_name = str(name)
                yield HermesProviderBlock(
                    f"auxiliary.{normalized_name}",
                    ("auxiliary", normalized_name),
                    block,
                )

    delegation = config.get("delegation")
    if isinstance(delegation, dict):
        yield HermesProviderBlock("delegation", ("delegation",), delegation)

    providers = config.get("providers")
    if isinstance(providers, dict):
        for name, block in providers.items():
            if isinstance(block, dict):
                normalized_name = str(name)
                yield HermesProviderBlock(
                    f"providers.{normalized_name}",
                    ("providers", normalized_name),
                    block,
                )

    fallback = config.get("fallback_providers")
    if isinstance(fallback, list):
        for index, block in enumerate(fallback):
            if isinstance(block, dict):
                yield HermesProviderBlock(
                    f"fallback_providers[{index}]",
                    (f"fallback_providers[{index}]",),
                    block,
                )

    custom = config.get("custom_providers")
    if isinstance(custom, list):
        for index, block in enumerate(custom):
            if isinstance(block, dict):
                yield HermesProviderBlock(
                    f"custom_providers[{index}]",
                    (f"custom_providers[{index}]",),
                    block,
                    is_custom=True,
                )


def block_field_path(block: HermesProviderBlock, field: str) -> tuple[str, ...]:
    return (*block.key_path, field)


def block_model_field(block: HermesProviderBlock) -> str:
    if block.group_path == "model":
        return "default"
    if block.group_path.startswith("providers."):
        return "default_model"
    return "model"


__all__ = [
    "HermesProviderBlock",
    "block_field_path",
    "block_model_field",
    "iter_hermes_provider_blocks",
]
