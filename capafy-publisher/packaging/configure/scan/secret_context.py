from __future__ import annotations

from packaging.configure.sensitive.keywords import key_tokens, normalize_key_name

CONTEXTUAL_KEY_SECRET_MARKERS = {
    "api",
    "auth",
    "credential",
    "credentials",
    "proactor",
    "provider",
    "providers",
    "secret",
    "secrets",
    "token",
    "tokens",
}


def is_contextual_secret_key(path_parts: list[str], key: str) -> bool:
    if "key" not in set(key_tokens(key)) and normalize_key_name(key) != "key":
        return False
    context_tokens = {
        normalize_key_name(part)
        for part in [*path_parts[:-1], *key_tokens(key)]
        if part and not str(part).startswith("[")
    }
    return bool(context_tokens & CONTEXTUAL_KEY_SECRET_MARKERS)


__all__ = [
    "CONTEXTUAL_KEY_SECRET_MARKERS",
    "is_contextual_secret_key",
]
