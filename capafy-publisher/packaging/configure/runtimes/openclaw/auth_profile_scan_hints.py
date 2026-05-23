from __future__ import annotations

import json
from typing import Callable

from packaging._shared.common.url_values import build_config_url_proxy_group, find_domains, normalize_explicit_url
from packaging._shared.openclaw.official_providers import (
    OpenClawOfficialProviderSpec,
    find_openclaw_official_provider_in_text,
)
from packaging.configure.scan.support import append_candidate
from packaging.configure.sensitive.keywords import contains_explicit_secret_keyword
from packaging.configure.sensitive.literals import extract_secret_value


OPENCLAW_CONFIG_REL_SOURCE = ".openclaw/openclaw.json"
OPENCLAW_AUTH_PROFILE_REL_SOURCE = ".openclaw/agents/main/agent/auth-profiles.json"


def _openclaw_url_proxy_group(path_parts: list[str], *, source_path: str = OPENCLAW_CONFIG_REL_SOURCE) -> str:
    return build_config_url_proxy_group(source_path, path_parts)


def _extract_provider_url(provider_config: dict) -> str | None:
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


def _infer_auth_profile_provider_spec(
    path_parts: list[str],
    node: dict,
) -> OpenClawOfficialProviderSpec | None:
    def match_text(value: str) -> OpenClawOfficialProviderSpec | None:
        return find_openclaw_official_provider_in_text(value)

    for key in ("provider", "type", "service", "name"):
        value = node.get(key)
        if isinstance(value, str):
            matched = match_text(value)
            if matched:
                return matched
    for part in reversed(path_parts):
        matched = match_text(part)
        if matched:
            return matched
    return None


def _auth_profile_provider_group(provider_name: str) -> str:
    return _openclaw_url_proxy_group(
        ["models", "providers", provider_name],
        source_path=OPENCLAW_CONFIG_REL_SOURCE,
    )


def _auth_profile_provider_field(provider_name: str, field: str) -> str:
    return f"models.providers.{provider_name}.{field}"


def _is_auth_profile_api_key_field(key_name: str) -> bool:
    return key_name.strip().lower() == "key" or contains_explicit_secret_keyword(key_name)


def collect_openclaw_auth_profile_scan_hints(
    text: str,
    annotate_candidate: Callable[[dict, str], dict | None],
) -> tuple[dict[str, str], dict[str, str], dict[str, str], list[dict]]:
    env_hints: dict[str, str] = {}
    service_hints: dict[str, str] = {}
    value_hints: dict[str, str] = {}
    explicit_candidates: list[dict] = []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return env_hints, service_hints, value_hints, []

    def walk(node: object, path_parts: list[str], inherited_domain: str | None = None) -> None:
        if isinstance(node, dict):
            explicit_domain = _extract_provider_url(node)
            provider_spec = _infer_auth_profile_provider_spec(path_parts, node)
            official_domain = provider_spec.base_url if provider_spec else ""
            domain = explicit_domain or official_domain or inherited_domain
            if not provider_spec:
                for key, value in node.items():
                    walk(value, path_parts + [str(key)], domain)
                return
            provider_name = provider_spec.provider_name
            url_proxy_group = _auth_profile_provider_group(provider_name)
            service_name = provider_spec.service
            api_key_field = _auth_profile_provider_field(provider_name, "apiKey")
            base_url_field = _auth_profile_provider_field(provider_name, "baseUrl")

            url_candidate_added = False
            api_key_candidate_added = False
            for key, value in node.items():
                if not isinstance(value, str):
                    continue
                key_name = str(key)
                if _is_auth_profile_api_key_field(key_name):
                    extracted_value = extract_secret_value(key_name, value)
                    if not extracted_value or not domain:
                        continue
                    value_hints.setdefault(extracted_value, domain)
                    append_candidate(
                        explicit_candidates,
                        annotate_candidate(
                            {
                                "entry_type": "api_key",
                                "field": api_key_field,
                                "value_type": None,
                                "value": extracted_value,
                                "service": service_name,
                                "default_url": domain,
                                "local_url": domain,
                                "source": OPENCLAW_CONFIG_REL_SOURCE,
                                "env_name": None,
                                "url_proxy_group": url_proxy_group,
                            },
                            OPENCLAW_AUTH_PROFILE_REL_SOURCE,
                        )
                    )
                    api_key_candidate_added = True
                    continue
                if not url_candidate_added and domain and key_name.lower() in {"provider", "type", "service", "name"}:
                    append_candidate(
                        explicit_candidates,
                        annotate_candidate(
                            {
                                "entry_type": "managed_value",
                                "field": base_url_field,
                                "value_type": "url",
                                "value": domain,
                                "service": service_name,
                                "default_url": domain,
                                "local_url": domain,
                                "source": OPENCLAW_CONFIG_REL_SOURCE,
                                "env_name": None,
                                "url_proxy_group": url_proxy_group,
                            },
                            OPENCLAW_AUTH_PROFILE_REL_SOURCE,
                        )
                    )
                    value_hints.setdefault(domain, domain)
                    url_candidate_added = True

            if domain and not url_candidate_added and (api_key_candidate_added or explicit_domain):
                append_candidate(
                    explicit_candidates,
                    annotate_candidate(
                        {
                            "entry_type": "managed_value",
                            "field": base_url_field,
                            "value_type": "url",
                            "value": domain,
                            "service": service_name,
                            "default_url": domain,
                            "local_url": domain,
                            "source": OPENCLAW_CONFIG_REL_SOURCE,
                            "env_name": None,
                            "url_proxy_group": url_proxy_group,
                        },
                        OPENCLAW_AUTH_PROFILE_REL_SOURCE,
                    )
                )
                value_hints.setdefault(domain, domain)

            for key, value in node.items():
                walk(value, path_parts + [str(key)], domain)
            return
        if isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, path_parts + [str(index)], inherited_domain)

    walk(payload, [])
    return env_hints, service_hints, value_hints, explicit_candidates


__all__ = [
    "OPENCLAW_AUTH_PROFILE_REL_SOURCE",
    "OPENCLAW_CONFIG_REL_SOURCE",
    "collect_openclaw_auth_profile_scan_hints",
]
