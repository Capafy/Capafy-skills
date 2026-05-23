from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Callable

from packaging.configure.sensitive.keywords import (
    contains_explicit_secret_keyword,
    contains_explicit_value_keyword,
)
from packaging.configure.sensitive.literals import (
    extract_assignment_value,
    extract_secret_value,
    infer_managed_value_type,
    looks_like_url_or_dsn,
)
from packaging.configure.scan.support import append_candidate as _append_candidate
from packaging._shared.common.url_values import build_config_url_proxy_group, find_domains, normalize_explicit_url
from packaging.configure.runtimes.openclaw.auth_profile_scan_hints import (
    collect_openclaw_auth_profile_scan_hints,
)
from packaging.configure.runtimes.openclaw.workspace_common import OPENCLAW_GENERIC_PATH_PARTS


_OPENCLAW_CONFIG_REL_SOURCE = ".openclaw/openclaw.json"
_OPENCLAW_PROVIDER_API_KEY_FIELDS = {"apiKey"}


def _openclaw_url_proxy_group(path_parts: list[str], *, source_path: str = _OPENCLAW_CONFIG_REL_SOURCE) -> str:
    return build_config_url_proxy_group(source_path, path_parts)


def _openclaw_provider_path_prefix(path_parts: list[str]) -> list[str] | None:
    lowered = [part.lower() for part in path_parts]
    for index in range(0, max(0, len(lowered) - 2)):
        if lowered[index] == "models" and lowered[index + 1] == "providers":
            return path_parts[: index + 3]
    return None


def _looks_like_openclaw_url_field(key_name: str, value: str) -> bool:
    lowered = key_name.strip().lower()
    if "url" not in lowered and "endpoint" not in lowered:
        return False
    return normalize_explicit_url(value) is not None


def collect_special_scan_candidates(
    path: Path,
    text: str,
    annotate_candidate: Callable[[dict, str], dict | None],
) -> tuple[dict[str, str], dict[str, str], dict[str, str], list[dict]]:
    if path.name == "auth-profiles.json":
        return collect_openclaw_auth_profile_scan_hints(text, annotate_candidate)
    if path.name != "openclaw.json":
        return {}, {}, {}, []
    return _collect_openclaw_scan_hints(text, annotate_candidate)


def should_scan_openclaw_structured_values(relpath: str) -> bool:
    return PurePosixPath(relpath).name.lower() not in {"openclaw.json", "auth-profiles.json"}


def _find_value_line_number(text: str, value: str) -> int | None:
    index = text.find(value)
    if index < 0:
        return None
    return text.count("\n", 0, index) + 1


def _infer_openclaw_service_name(path_parts: list[str], node: dict, inherited_service: str | None) -> str | None:
    provider = node.get("provider")
    if isinstance(provider, str) and provider.strip():
        return provider.strip()

    for part in reversed(path_parts):
        lowered = part.lower()
        if lowered in OPENCLAW_GENERIC_PATH_PARTS:
            continue
        if part.isdigit():
            continue
        return part
    return inherited_service


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


def _collect_openclaw_scan_hints(
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

    def walk(
        node: object,
        path_parts: list[str],
        inherited_domain: str | None = None,
        inherited_service: str | None = None,
        inherited_group: str | None = None,
    ) -> None:
        if isinstance(node, dict):
            skip_capture = any(part.lower() == "channels" for part in path_parts)

            service_name = _infer_openclaw_service_name(path_parts, node, inherited_service)
            explicit_domain = _extract_provider_url(node)
            provider_path_prefix = _openclaw_provider_path_prefix(path_parts)
            is_provider_context = provider_path_prefix is not None
            is_provider_node = provider_path_prefix == path_parts
            if explicit_domain and is_provider_context:
                url_proxy_group = _openclaw_url_proxy_group(provider_path_prefix)
            elif is_provider_context:
                url_proxy_group = inherited_group
            else:
                url_proxy_group = None
            domain = explicit_domain or inherited_domain
            if domain and service_name and not skip_capture:
                service_hints.setdefault(service_name.lower(), domain)
            for key, value in node.items():
                if not isinstance(value, str):
                    continue
                if re.fullmatch(r"[A-Z][A-Z0-9_]*", value):
                    if domain and not skip_capture:
                        env_hints.setdefault(value, domain)
                    continue
                key_name = str(key)
                if is_provider_node and domain and value == domain and not skip_capture:
                    _append_candidate(
                        explicit_candidates,
                        annotate_candidate(
                            {
                                "entry_type": "managed_value",
                                "field": key_name,
                                "value_type": "url",
                                "value": domain,
                                "service": service_name or "unknown",
                                "default_url": domain,
                                "local_url": domain,
                                "source": ".openclaw/openclaw.json",
                                "env_name": None,
                                "url_proxy_group": url_proxy_group or _openclaw_url_proxy_group(path_parts),
                            },
                            ".openclaw/openclaw.json",
                        )
                    )
                    value_hints.setdefault(domain, domain)
                    continue
                entry_type = "managed_value"
                value_type = infer_managed_value_type(key_name, value)
                if contains_explicit_secret_keyword(key_name):
                    extracted_value = extract_secret_value(key_name, value)
                    entry_type = "api_key"
                    value_type = None
                elif contains_explicit_value_keyword(key_name) or _looks_like_openclaw_url_field(key_name, value):
                    extracted_value = extract_assignment_value(key_name, value)
                    if not extracted_value and _looks_like_openclaw_url_field(key_name, value):
                        extracted_value = normalize_explicit_url(value)
                else:
                    continue
                if not extracted_value:
                    continue
                url_proxy_group_for_candidate = ""
                if is_provider_context and entry_type == "api_key" and key_name in _OPENCLAW_PROVIDER_API_KEY_FIELDS:
                    url_proxy_group_for_candidate = url_proxy_group or _openclaw_url_proxy_group(path_parts)
                managed_url = domain or "unknown"
                if looks_like_url_or_dsn(extracted_value):
                    managed_url = extracted_value.strip()
                if domain:
                    value_hints.setdefault(extracted_value, domain)
                line_no = _find_value_line_number(text, value) or _find_value_line_number(text, extracted_value)
                source = f".openclaw/openclaw.json line {line_no}" if line_no else ".openclaw/openclaw.json"
                _append_candidate(
                    explicit_candidates,
                    annotate_candidate(
                        {
                            "entry_type": entry_type,
                            "field": key_name,
                            "value_type": value_type,
                            "value": extracted_value,
                            "service": service_name or "unknown",
                            "default_url": managed_url,
                            "local_url": managed_url,
                            "source": source,
                            "env_name": None,
                            "url_proxy_group": url_proxy_group_for_candidate,
                        },
                        ".openclaw/openclaw.json",
                    )
                )
            for key, value in node.items():
                walk(value, path_parts + [str(key)], domain, service_name, url_proxy_group)
            return
        if isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, path_parts + [str(index)], inherited_domain, inherited_service, inherited_group)

    walk(payload, [])
    return env_hints, service_hints, value_hints, explicit_candidates
