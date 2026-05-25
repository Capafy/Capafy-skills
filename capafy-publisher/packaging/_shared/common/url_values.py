from __future__ import annotations
from typing import Optional

import ipaddress
import re
from urllib.parse import urlparse




DOMAIN_PATTERN = re.compile(r"https?://[^\s'\"<>]+|(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?:/[^\s'\"<>]*)?")


def has_http_url_scheme(value: str) -> bool:
    normalized = str(value or "").strip()
    if not normalized:
        return False
    try:
        parsed = urlparse(normalized)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _looks_like_host(value: str) -> bool:
    host = str(value or "").strip().lower()
    if not host:
        return False
    if host == "localhost":
        return True
    if ":" in host and host.startswith("[") and host.endswith("]"):
        return True
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return "." in host


def normalize_http_url_candidate(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    if has_http_url_scheme(normalized):
        return normalized
    if any(char.isspace() for char in normalized):
        return ""
    if "://" in normalized and not normalized.startswith("//"):
        return ""

    if normalized.startswith("//"):
        candidate = f"https:{normalized}"
    else:
        candidate = f"https://{normalized.lstrip('/')}"
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    if not _looks_like_host(parsed.hostname or ""):
        return ""
    return candidate


def _normalize_domain(candidate: str) -> Optional[str]:
    value = candidate.strip().rstrip(".,;:)]}")
    if not value:
        return None
    if "://" not in value:
        value = f"https://{value}"
    try:
        parsed = urlparse(value)
    except ValueError:
        return None
    host = parsed.netloc or parsed.path.split("/", 1)[0]
    host = host.strip().rstrip(".,;:)]}")
    if "." not in host:
        return None
    return host.lower()


def find_domains(text: str) -> list[str]:
    seen: list[str] = []
    for match in DOMAIN_PATTERN.finditer(text):
        domain = _normalize_domain(match.group(0))
        if domain and domain not in seen:
            seen.append(domain)
    return seen


def normalize_explicit_url(candidate: str) -> Optional[str]:
    value = candidate.strip().rstrip(".,;)]}")
    if not value:
        return None
    if "://" in value:
        try:
            parsed = urlparse(value)
        except ValueError:
            return None
        host = parsed.netloc or parsed.path.split("/", 1)[0]
        host = host.strip().rstrip(".,;:)]}")
        if "." in host:
            return value
    domains = find_domains(value)
    if domains:
        return domains[0]
    return None


def build_config_url_proxy_group(
    source_display_path: str,
    path_parts: object,
) -> str:
    if isinstance(path_parts, str):
        suffix = path_parts.strip()
    else:
        try:
            iterator = iter(path_parts)
        except TypeError:
            suffix = str(path_parts or "").strip()
        else:
            suffix = ".".join(str(part).strip() for part in iterator if str(part).strip())
    return f"{source_display_path}#{suffix}" if suffix else source_display_path


__all__ = [
    "build_config_url_proxy_group",
    "find_domains",
    "has_http_url_scheme",
    "normalize_explicit_url",
    "normalize_http_url_candidate",
]
