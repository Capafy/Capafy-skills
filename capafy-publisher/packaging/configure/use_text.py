from __future__ import annotations

def _label_or_fallback(value: str, fallback: str) -> str:
    label = str(value or "").strip()
    return label or fallback


def use_for_generic_value(
    field: str,
    value_type: str,
    *,
    service: str = "",
    url: str = "",
) -> str:
    label = str(field or "").strip() or str(service or "").strip()
    normalized_type = str(value_type or "").strip().lower()
    normalized_field = str(field or "").strip().lower()
    if normalized_type == "url" or str(url or "").strip() or "url" in normalized_field or "webhook" in normalized_field:
        return f"Service endpoint for {label}" if label else "Service endpoint"
    if normalized_type == "api_key" or any(
        marker in normalized_field
        for marker in ("api_key", "apikey", "access_key", "token", "secret", "password")
    ):
        return f"API key for {label}" if label else "API key"
    return f"Runtime value for {label}" if label else "Runtime value"


__all__ = [
    "use_for_generic_value",
]
