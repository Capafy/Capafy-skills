from __future__ import annotations

import re
from urllib.parse import urlparse

from packaging.publish.security.sensitive.keywords import contains_explicit_secret_keyword
from packaging.publish.security.sensitive.literals import (
    extract_assignment_value,
    extract_secret_value,
    infer_managed_value_type,
)
from packaging.common.url_values import find_domains

from .candidate_annotation import annotate_candidate
from .structured_scan_policy import infer_assignment_service
from .support import append_candidate, pick_domain


NETRC_MACHINE_PATTERN = re.compile(r"(?ms)^\s*machine\s+(?P<host>\S+)(?P<body>.*?)(?=^\s*(?:machine|default|macdef)\b|\Z)")
NETRC_FIELD_PATTERN = re.compile(r"\b(login|password|account)\s+(\S+)")
XML_TAG_VALUE_PATTERN = re.compile(
    r"<(?P<key>username|password|passphrase|privateKey|private_key|token|apikey|apiKey|authToken|clientSecret|clientId)>"
    r"\s*(?P<value>[^<]+?)\s*</(?P=key)>",
    re.IGNORECASE,
)
XML_ADD_VALUE_PATTERN = re.compile(
    r"<add\b[^>]*\bkey\s*=\s*['\"](?P<key>[^'\"]+)['\"][^>]*\bvalue\s*=\s*['\"](?P<value>[^'\"]+)['\"][^>]*/?>",
    re.IGNORECASE,
)
RUBYGEMS_CREDENTIAL_PATTERN = re.compile(r"^\s*:(?P<key>[A-Za-z_][A-Za-z0-9_.-]{1,120})\s*:\s*(?P<value>.+?)\s*$")


def _collect_netrc_candidates(text: str, relpath: str) -> list[dict]:
    lowered = relpath.lower()
    if not (lowered.endswith(".netrc") or lowered.endswith("_netrc")):
        return []
    candidates: list[dict] = []
    for match in NETRC_MACHINE_PATTERN.finditer(text):
        host = match.group("host")
        body = match.group("body")
        fields = {field.lower(): value for field, value in NETRC_FIELD_PATTERN.findall(body)}
        line_no = text.count("\n", 0, match.start()) + 1
        source = f"{relpath} line {line_no}"
        url = host.lower()
        if "login" in fields:
            append_candidate(
                candidates,
                annotate_candidate(
                    {
                        "entry_type": "managed_value",
                        "field": "login",
                        "value_type": "login_identifier",
                        "value": fields["login"],
                        "service": "Login",
                        "default_url": url,
                        "local_url": url,
                        "source": source,
                        "env_name": None,
                    },
                    relpath,
                )
            )
        for secret_key in ("password", "account"):
            secret_value = fields.get(secret_key)
            if not secret_value:
                continue
            append_candidate(
                candidates,
                annotate_candidate(
                    {
                        "entry_type": "api_key",
                        "field": secret_key,
                        "value": secret_value,
                        "service": "Login",
                        "default_url": url,
                        "local_url": url,
                        "source": source,
                        "env_name": None,
                    },
                    relpath,
                )
            )
    return candidates


def _collect_git_credentials_candidates(text: str, relpath: str) -> list[dict]:
    if not relpath.lower().endswith(".git-credentials"):
        return []
    candidates: list[dict] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or "://" not in line:
            continue
        try:
            parsed = urlparse(line)
        except ValueError:
            continue
        host = parsed.hostname
        if not host:
            continue
        url = host.lower()
        source = f"{relpath} line {line_no}"
        if parsed.username:
            append_candidate(
                candidates,
                annotate_candidate(
                    {
                        "entry_type": "managed_value",
                        "field": "username",
                        "value_type": "login_identifier",
                        "value": parsed.username,
                        "service": "Git",
                        "default_url": url,
                        "local_url": url,
                        "source": source,
                        "env_name": None,
                    },
                    relpath,
                )
            )
        if parsed.password:
            append_candidate(
                candidates,
                annotate_candidate(
                    {
                        "entry_type": "api_key",
                        "field": "password",
                        "value": parsed.password,
                        "service": "Git",
                        "default_url": url,
                        "local_url": url,
                        "source": source,
                        "env_name": None,
                    },
                    relpath,
                )
            )
    return candidates


def _collect_xml_value_candidates(text: str, relpath: str) -> list[dict]:
    lowered = relpath.lower()
    is_maven_settings = lowered.endswith(".m2/settings.xml")
    is_nuget_config = lowered.endswith("nuget.config")
    if not (is_maven_settings or is_nuget_config):
        return []
    candidates: list[dict] = []
    service = infer_assignment_service(relpath, "", "")
    default_url = pick_domain(find_domains(text), service, "unknown")
    patterns = (XML_TAG_VALUE_PATTERN, XML_ADD_VALUE_PATTERN)
    for pattern in patterns:
        for match in pattern.finditer(text):
            key = match.group("key")
            value = match.group("value")
            entry_type = "managed_value"
            value_type = infer_managed_value_type(key, value)
            if contains_explicit_secret_keyword(key):
                extracted_value = extract_secret_value(key, value)
                entry_type = "api_key"
                value_type = None
            else:
                extracted_value = extract_assignment_value(key, value)
            if not extracted_value:
                continue
            line_no = text.count("\n", 0, match.start()) + 1
            append_candidate(
                candidates,
                annotate_candidate(
                    {
                        "entry_type": entry_type,
                        "field": key,
                        "value_type": value_type,
                        "value": extracted_value,
                        "service": service,
                        "default_url": default_url,
                        "local_url": default_url,
                        "source": f"{relpath} line {line_no}",
                        "env_name": None,
                    },
                    relpath,
                )
            )
    return candidates


def _collect_rubygems_candidates(text: str, relpath: str) -> list[dict]:
    if not relpath.lower().endswith(".gem/credentials"):
        return []
    candidates: list[dict] = []
    default_url = "rubygems.org"
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        match = RUBYGEMS_CREDENTIAL_PATTERN.match(raw_line.rstrip("\r\n"))
        if not match:
            continue
        key = match.group("key")
        extracted_value = extract_assignment_value(key, match.group("value"))
        if not extracted_value:
            continue
        entry_type = "api_key" if contains_explicit_secret_keyword(key) else "managed_value"
        append_candidate(
            candidates,
            annotate_candidate(
                {
                    "entry_type": entry_type,
                    "field": key,
                    "value_type": None if entry_type == "api_key" else infer_managed_value_type(key, extracted_value),
                    "value": extracted_value,
                    "service": "RubyGems",
                    "default_url": default_url,
                    "local_url": default_url,
                    "source": f"{relpath} line {line_no}",
                    "env_name": None,
                },
                relpath,
            )
        )
    return candidates


def collect_special_file_candidates(text: str, relpath: str) -> list[dict]:
    candidates: list[dict] = []
    candidates.extend(_collect_netrc_candidates(text, relpath))
    candidates.extend(_collect_git_credentials_candidates(text, relpath))
    candidates.extend(_collect_xml_value_candidates(text, relpath))
    candidates.extend(_collect_rubygems_candidates(text, relpath))
    return candidates
