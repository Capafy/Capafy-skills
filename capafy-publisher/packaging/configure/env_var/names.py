from __future__ import annotations

from packaging.configure.contracts import PROCESS_ENV_SOURCE


PROCESS_ENV_IGNORED_NAMES = {
    "OLDPWD",
    "PWD",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "ALL_PROXY",
    "FTP_PROXY",
    "SOCKS_PROXY",
}

PROCESS_ENV_SECRET_SUFFIXES = (
    "_API_KEY",
    "_ACCESS_TOKEN",
    "_AUTH_TOKEN",
    "_BEARER_TOKEN",
    "_TOKEN",
    "_SECRET_KEY",
    "_SECRET",
    "_AUTHORIZATION",
    "_KEY",
)

PROCESS_ENV_URL_SUFFIXES = (
    "_API_BASE_URL",
    "_BASE_URL",
    "_API_URL",
    "_ENDPOINT",
    "_URL",
)


def iter_related_process_env_names(env_name: str) -> set[str]:
    related: set[str] = set()
    suffix_group = PROCESS_ENV_SECRET_SUFFIXES + PROCESS_ENV_URL_SUFFIXES
    for suffix in suffix_group:
        if not env_name.endswith(suffix) or len(env_name) <= len(suffix):
            continue
        stem = env_name[: -len(suffix)]
        for peer_suffix in suffix_group:
            if peer_suffix != suffix:
                related.add(f"{stem}{peer_suffix}")
        break
    return related


__all__ = [
    "PROCESS_ENV_IGNORED_NAMES",
    "PROCESS_ENV_SECRET_SUFFIXES",
    "PROCESS_ENV_SOURCE",
    "PROCESS_ENV_URL_SUFFIXES",
    "iter_related_process_env_names",
]
