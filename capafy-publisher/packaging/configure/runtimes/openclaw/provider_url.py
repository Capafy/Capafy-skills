from __future__ import annotations
from typing import Optional

import json

from packaging._shared.common.url_values import find_domains, normalize_explicit_url


def extract_provider_url(provider_config: dict) -> Optional[str]:
    preferred_keys = (
        "baseUrl",
        "baseURL",
        "apiBase",
        "api_base",
        "endpoint",
        "url",
    )
    for key in preferred_keys:
        value = provider_config.get(key)
        if isinstance(value, str):
            explicit_url = normalize_explicit_url(value)
            if explicit_url:
                return explicit_url

    domains = find_domains(json.dumps(provider_config, ensure_ascii=False))
    if domains:
        return domains[0]
    return None


__all__ = [
    "extract_provider_url",
]
