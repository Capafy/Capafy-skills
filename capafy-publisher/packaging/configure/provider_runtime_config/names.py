from __future__ import annotations

PROXY_ENVIRONMENT_NAMES = frozenset({
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "ALL_PROXY",
    "FTP_PROXY",
    "SOCKS_PROXY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
    "all_proxy",
    "ftp_proxy",
    "socks_proxy",
})

ENVIRONMENT_HINT_IGNORED_NAMES = frozenset({
    "CODEX_HOME",
    "OLDPWD",
    "PWD",
    *PROXY_ENVIRONMENT_NAMES,
})

__all__ = [
    "ENVIRONMENT_HINT_IGNORED_NAMES",
    "PROXY_ENVIRONMENT_NAMES",
]
