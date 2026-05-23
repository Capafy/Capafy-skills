from __future__ import annotations

from packaging.configure.exclusion import EXCLUDE_FILE_SUFFIXES


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


def use_for_env_var(name: str) -> str:
    return f"Environment variable {_label_or_fallback(name, 'value')}"


def use_for_excluded_file(source: str, reason: str) -> str:
    normalized_source = str(source or "").strip().lower()
    reason_code = str(reason or "").strip()
    if reason_code == "private_key":
        return "Private key file excluded from package"
    if reason_code == "cert":
        return "Certificate or keystore file excluded from package"
    if any(normalized_source.endswith(suffix) for suffix in EXCLUDE_FILE_SUFFIXES):
        return "Login credential file excluded from package"
    return "Credential file excluded from package"


__all__ = [
    "use_for_env_var",
    "use_for_excluded_file",
    "use_for_generic_value",
]
