from __future__ import annotations

from typing import Any, TYPE_CHECKING

from packaging._shared.contracts.reviewed_scan import build_reviewed_env_var_item
from packaging.configure.use_text import (
    use_for_env_var,
    use_for_excluded_file,
    use_for_generic_value,
)

if TYPE_CHECKING:
    from packaging.configure.contracts import ReviewedScanBuildInput


def build_reviewed_scan_from_input(
    reviewed_input: ReviewedScanBuildInput,
    *,
    review_binding: dict[str, str],
) -> dict[str, Any]:
    review_metadata = {
        "reviewer": "rules_scan",
        "status": "reviewed",
    }
    review_metadata.update(review_binding)

    url_proxy_items: list[dict[str, Any]] = []
    for pair in reviewed_input.url_proxy_pairs:
        item = {
            "api_key": {
                "value": pair.key.original_value,
                "placeholder": pair.key.placeholder,
                "field": pair.key.field,
                "source": pair.key.source_identity(),
                "source_detail": pair.key.source_detail_identity(),
                "occurrence_index": pair.key.occurrence_index_identity(),
            },
            "url": {
                "value": pair.url.original_value,
                "placeholder": pair.url.placeholder,
                "field": pair.url.field,
                "source": pair.url.source_identity(),
                "source_detail": pair.url.source_detail_identity(),
                "occurrence_index": pair.url.occurrence_index_identity(),
                "value_type": "url",
                "url": pair.url.original_value or pair.url.placeholder,
            },
            "url_proxy_group": pair.group,
            "use": f"API key and endpoint for {pair.key.field}",
        }
        model = str(pair.model or "").strip()
        api_format = str(pair.api_format or "").strip()
        if model:
            item["model"] = model
        if api_format:
            item["api_format"] = api_format
        url_proxy_items.append(item)

    generic_items: list[dict[str, Any]] = []
    for generic_value in reviewed_input.generic_values:
        source = str(generic_value.source_relpath or "").strip()
        if not source:
            continue
        generic_items.append({
            "value": generic_value.original_value,
            "placeholder": generic_value.placeholder,
            "field": generic_value.field,
            "source": source,
            "source_detail": generic_value.location.to_source_detail(generic_value.field),
            "occurrence_index": generic_value.location.occurrence_index_identity(),
            "value_type": generic_value.value_type,
            "use": use_for_generic_value(generic_value.field, generic_value.value_type),
        })

    env_var_items: list[dict[str, Any]] = []
    for env_var in reviewed_input.env_vars:
        env_var_items.append(
            build_reviewed_env_var_item(
                field=env_var.name,
                value=env_var.process_value,
                placeholder=env_var.placeholder,
                referenced_in=env_var.referenced_in,
                use=use_for_env_var(env_var.name),
            )
        )

    exclude_items: list[dict[str, Any]] = []
    for excluded_file in reviewed_input.excludes:
        exclude_items.append({
            "source": excluded_file.source,
            "reason": excluded_file.reason,
            "use": use_for_excluded_file(excluded_file.source, excluded_file.reason),
        })

    return {
        "url_proxy": url_proxy_items,
        "generic": generic_items,
        "env_var": env_var_items,
        "excludes": exclude_items,
        "_review": review_metadata,
    }


__all__ = ["build_reviewed_scan_from_input"]
