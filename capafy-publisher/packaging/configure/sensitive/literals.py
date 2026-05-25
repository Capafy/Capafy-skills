from __future__ import annotations
from typing import Optional

import re

from packaging._shared.common.constants import (
    APP_IDENTIFIER_PATTERNS,
    AUTH_SCHEME_PATTERN,
    DSN_VALUE_PATTERN,
)
from packaging.configure.sensitive.keywords import (
    contains_explicit_secret_keyword,
    contains_explicit_value_keyword,
    contains_login_identifier_keyword,
    is_database_setting_key,
    is_password_secret_key,
    normalize_key_name,
)


_IDENTIFIER_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{5,255}$")
_NON_LITERAL_REFERENCE_PATTERNS = [
    re.compile(r"^\$\{?[A-Z][A-Z0-9_]*\}?$"),
    re.compile(r"^\$\(.*\)$"),
    re.compile(r"^os\.(?:getenv|environ)\(.+\)$"),
    re.compile(r"^process\.env\.[A-Za-z_][A-Za-z0-9_]*$"),
]

_LOGIN_IDENTIFIER_USER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@+-]{2,127}$")
_LOGIN_IDENTIFIER_EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_LOGIN_IDENTIFIER_PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9()\-\s]{5,31}$")
_PASSWORD_SAMPLE_VALUES = {
    "password",
    "passwd",
    "pwd",
    "pass",
    "admin",
    "root",
    "secret",
    "changeme",
    "change_me",
    "letmein",
    "123456",
}


def extract_secret_value(key: str, value: str) -> Optional[str]:
    stripped = value.strip()
    if not stripped:
        return None
    if re.fullmatch(r"[A-Z][A-Z0-9_]*", stripped):
        return None

    lowered_key = key.lower()
    if "authorization" in lowered_key or lowered_key == "auth":
        match = AUTH_SCHEME_PATTERN.match(stripped)
        if match:
            return match.group(2).strip()
    return stripped


def looks_like_reference_or_expression(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return True
    if any(pattern.fullmatch(stripped) for pattern in _NON_LITERAL_REFERENCE_PATTERNS):
        return True
    expression_tokens = ("${", "$(", "`", " + ", " if ", " else ", " and ", " or ")
    if any(token in stripped for token in expression_tokens):
        return True
    if any(char in stripped for char in "[]{}()"):
        if not looks_like_url_or_dsn(stripped):
            return True
    return False


def looks_like_secret_literal(value: str) -> bool:
    stripped = value.strip()
    if not stripped or looks_like_reference_or_expression(stripped):
        return False
    if looks_like_url_or_dsn(stripped):
        return True
    if looks_like_app_identifier(stripped):
        return True
    if any(char.isspace() for char in stripped):
        return False
    if len(stripped) < 6:
        return False
    if not re.fullmatch(r"[A-Za-z0-9_./:=+-]+", stripped):
        return False
    has_alpha = any(char.isalpha() for char in stripped)
    has_digit = any(char.isdigit() for char in stripped)
    has_symbol = any(not char.isalnum() for char in stripped)
    if has_alpha and has_digit:
        return True
    if has_alpha and has_symbol and len(stripped) >= 8:
        return True
    return False


def looks_like_password_literal(value: str) -> bool:
    stripped = value.strip()
    if not stripped or looks_like_reference_or_expression(stripped):
        return False
    if looks_like_placeholder_value(stripped):
        return False
    if stripped.lower() in _PASSWORD_SAMPLE_VALUES:
        return False
    if any(ord(char) < 33 or ord(char) > 126 for char in stripped):
        return False
    if len(stripped) < 6:
        return False
    has_alpha = any(char.isalpha() for char in stripped)
    has_digit = any(char.isdigit() for char in stripped)
    has_symbol = any(not char.isalnum() for char in stripped)
    if has_alpha and (has_digit or has_symbol):
        return True
    if has_digit and has_symbol:
        return True
    return has_alpha and len(stripped) >= 12


def _looks_like_secret_list_literal(value: str) -> bool:
    parts = [part.strip() for part in re.split(r"[;,]", value.strip()) if part.strip()]
    if len(parts) < 2:
        return False
    return all(looks_like_secret_literal(part) for part in parts)


def looks_like_config_literal(value: str) -> bool:
    stripped = value.strip()
    if not stripped or looks_like_reference_or_expression(stripped):
        return False
    if looks_like_url_or_dsn(stripped):
        return True
    if looks_like_app_identifier(stripped):
        return True
    if any(char in stripped for char in "<>"):
        return False
    if any(char.isspace() for char in stripped):
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_.:/@=+-]{1,255}", stripped))


def looks_like_login_identifier_literal(value: str) -> bool:
    stripped = value.strip()
    if not stripped or looks_like_reference_or_expression(stripped):
        return False
    if looks_like_placeholder_value(stripped):
        return False
    if looks_like_url_or_dsn(stripped):
        return False
    if any(char in stripped for char in "<>{}[]"):
        return False
    if _LOGIN_IDENTIFIER_EMAIL_PATTERN.fullmatch(stripped):
        return True
    if _LOGIN_IDENTIFIER_PHONE_PATTERN.fullmatch(stripped):
        digits = sum(char.isdigit() for char in stripped)
        return digits >= 6
    return bool(_LOGIN_IDENTIFIER_USER_PATTERN.fullmatch(stripped))


def strip_literal_value(raw: str) -> str:
    value = raw.strip()
    while value.endswith((",", ";")):
        value = value[:-1].rstrip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value.strip()


def looks_like_placeholder_value(value: str) -> bool:
    lowered = value.strip().lower()
    if not lowered:
        return True
    if lowered == "platform_managed_key":
        return True
    if lowered.startswith("platform_managed_value_"):
        return True
    placeholders = (
        "example",
        "sample",
        "placeholder",
        "changeme",
        "change_me",
        "replace_me",
        "your_",
        "your-",
        "<",
        "...",
    )
    if lowered in {"null", "none", "true", "false", "string", "number", "boolean"}:
        return True
    return any(token in lowered for token in placeholders)


def looks_like_platform_managed_placeholder_value(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered == "platform_managed_key" or lowered.startswith("platform_managed_value_")


def looks_like_url_or_dsn(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    if "://" in stripped:
        return True
    return bool(DSN_VALUE_PATTERN.match(stripped))


def looks_like_app_identifier(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    return any(pattern.fullmatch(stripped) for pattern in APP_IDENTIFIER_PATTERNS)


def infer_managed_value_type(key: str, value: str) -> str:
    normalized = normalize_key_name(key)
    stripped = value.strip()
    if stripped.startswith("jdbc:") or DSN_VALUE_PATTERN.match(stripped):
        return "dsn"
    if looks_like_url_or_dsn(stripped):
        return "url"
    if contains_login_identifier_keyword(key):
        return "login_identifier"
    if "appid" in normalized:
        return "app_id"
    if "appleid" in normalized:
        return "apple_id"
    if "googleid" in normalized:
        return "google_id"
    if "appsecret" in normalized:
        return "app_secret"
    if "clientid" in normalized:
        return "client_id"
    if "clientsecret" in normalized:
        return "client_secret"
    if "tenantkey" in normalized:
        return "tenant_key"
    if "tenantid" in normalized:
        return "tenant_id"
    if "accountsid" in normalized:
        return "account_id"
    if "webhook" in normalized:
        return "webhook"
    if "proxy" in normalized:
        return "proxy"
    return "value"


def extract_assignment_value(key: str, value: str) -> Optional[str]:
    normalized_key = normalize_key_name(key)
    stripped = strip_literal_value(value)
    if not stripped or looks_like_placeholder_value(stripped):
        return None
    if re.fullmatch(r"[A-Z][A-Z0-9_]*", stripped):
        return None
    if looks_like_reference_or_expression(stripped):
        return None

    if contains_explicit_secret_keyword(key):
        secret_value = extract_secret_value(key, stripped)
        if secret_value and (
            looks_like_secret_literal(secret_value)
            or (is_password_secret_key(key) and looks_like_password_literal(secret_value))
            or (normalize_key_name(key).endswith("apikeys") and _looks_like_secret_list_literal(secret_value))
        ):
            return secret_value
        return None
    if contains_explicit_value_keyword(key):
        if looks_like_url_or_dsn(stripped):
            return stripped
        if any(token in normalized_key for token in ("appid", "appleid", "googleid", "clientid", "tenantkey", "tenantid")):
            if looks_like_app_identifier(stripped):
                return stripped
            return None
        if is_database_setting_key(key):
            if looks_like_config_literal(stripped):
                return stripped
            return None
        if _IDENTIFIER_VALUE_PATTERN.match(stripped):
            return stripped
    if contains_login_identifier_keyword(key):
        if looks_like_login_identifier_literal(stripped):
            return stripped
    return None


__all__ = [
    "extract_assignment_value",
    "extract_secret_value",
    "infer_managed_value_type",
    "looks_like_placeholder_value",
    "looks_like_platform_managed_placeholder_value",
    "looks_like_secret_literal",
    "looks_like_url_or_dsn",
    "strip_literal_value",
]
