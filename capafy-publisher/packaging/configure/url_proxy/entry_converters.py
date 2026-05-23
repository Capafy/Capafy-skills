from __future__ import annotations

from packaging.configure.contracts import FieldLocation, PlanField, SourceKind, UrlProxyPair
from packaging.configure.scan.entry_finalize import entry_source, finalize_entry


def _item_value(item: dict, key: str) -> str:
    return str(item.get(key, "") or "").strip()


def _source_kind_from_entry_source(source: str) -> SourceKind:
    return SourceKind.PROCESS_ENV if source == "process.env" else SourceKind.FILE


def _plan_field_from_url_proxy_entry_side(item: dict, *, service: str) -> PlanField:
    source = _item_value(item, "source")
    return PlanField(
        field=_item_value(item, "field"),
        service=service,
        source_kind=_source_kind_from_entry_source(source),
        source_relpath="" if source == "process.env" else source,
        location=FieldLocation(fmt="json"),
        original_value=_item_value(item, "value"),
        placeholder=_item_value(item, "placeholder"),
        reviewed_source_detail=_item_value(item, "source_detail"),
        reviewed_occurrence_index=int(item.get("occurrence_index", 1) or 1),
    )


def build_url_proxy_entry(key_entry: dict, url_entry: dict) -> dict:
    finalized_key = finalize_entry(key_entry)
    finalized_url = finalize_entry(url_entry)
    api_field = str(finalized_key.get("field", "")).strip() or finalized_key["service"]
    url_proxy_group = str(key_entry.get("url_proxy_group") or url_entry.get("url_proxy_group") or "").strip()
    result = {
        "api_key": {
            "value": finalized_key["value"],
            "placeholder": finalized_key["placeholder"],
            "field": finalized_key.get("field", ""),
            "source": entry_source(key_entry),
            "source_detail": finalized_key.get("source_detail", ""),
            "occurrence_index": finalized_key.get("occurrence_index", 1),
            "url": finalized_key.get("url", ""),
        },
        "url": {
            "value": finalized_url["value"],
            "placeholder": finalized_url["placeholder"],
            "field": finalized_url.get("field", ""),
            "source": entry_source(url_entry),
            "source_detail": finalized_url.get("source_detail", ""),
            "occurrence_index": finalized_url.get("occurrence_index", 1),
            "value_type": finalized_url.get("value_type", "url"),
            "url": finalized_url.get("url", ""),
        },
        "use": f"API key and endpoint for {api_field}",
    }
    if url_proxy_group:
        result["url_proxy_group"] = url_proxy_group
    return result


def url_proxy_entry_to_pair(
    entry: dict,
    *,
    default_contract_id: str,
) -> UrlProxyPair | None:
    api_key = entry.get("api_key")
    url = entry.get("url")
    if not isinstance(api_key, dict) or not isinstance(url, dict):
        return None
    service = _item_value(api_key, "service") or _item_value(url, "service") or "Service"
    group = _item_value(entry, "url_proxy_group") or f"<{default_contract_id}>"
    return UrlProxyPair(
        contract_id=default_contract_id,
        service=service,
        group=group,
        key=_plan_field_from_url_proxy_entry_side(api_key, service=service),
        url=_plan_field_from_url_proxy_entry_side(url, service=service),
        is_synthesized=False,
        model=_item_value(entry, "model"),
        api_format=_item_value(entry, "api_format"),
    )


__all__ = [
    "build_url_proxy_entry",
    "url_proxy_entry_to_pair",
]
