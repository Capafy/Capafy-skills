from __future__ import annotations

import re

from packaging._shared.common.constants import STRUCTURED_ASSIGNMENT_PATTERNS
from packaging._shared.common.url_values import find_domains
from packaging.configure.sensitive.literals import extract_assignment_value

from packaging.configure.scan.candidate_annotation import annotate_candidate
from packaging.configure.scan.support import pick_domain


GENERIC_API_KEY_PATTERNS = (
    ("Anthropic", "api.anthropic.com", re.compile(r"sk-ant-[A-Za-z0-9_-]{6,}")),
    ("OpenAI", "api.openai.com", re.compile(r"sk-proj-[A-Za-z0-9_-]{6,}")),
    ("Google", "googleapis.com", re.compile(r"AIza[0-9A-Za-z_-]{10,}")),
    ("AWS", "amazonaws.com", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub", "api.github.com", re.compile(r"(?:ghp_|gho_|ghs_)[A-Za-z0-9]{10,}")),
    ("GitHub", "api.github.com", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("Slack", "slack.com", re.compile(r"xox(?:b|p)-[A-Za-z0-9-]{10,}")),
    ("SendGrid", "api.sendgrid.com", re.compile(r"SG\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
    ("Stripe", "api.stripe.com", re.compile(r"sk_(?:live|test)_[A-Za-z0-9]{12,}")),
    ("Stripe", "api.stripe.com", re.compile(r"rk_(?:live|test)_[A-Za-z0-9]{12,}")),
    ("Stripe", "api.stripe.com", re.compile(r"whsec_[A-Za-z0-9]{12,}")),
    ("PyPI", "upload.pypi.org", re.compile(r"pypi-[A-Za-z0-9_-]{20,}")),
    ("Apify", "api.apify.com", re.compile(r"apify_api_[A-Za-z0-9]{10,}")),
)
ENV_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{1,127}$")
FIELD_BEFORE_VALUE_PATTERN = re.compile(
    r"(?:^|[\s,{;])(?:export\s+)?(?:const\s+|let\s+|var\s+)?"
    r"(?P<field>[A-Za-z_][A-Za-z0-9_.-]{0,120})\s*[:=]\s*['\"]?\s*$"
)


def _field_before_match(line: str, start_col: int, service: str) -> str:
    prefix = line[:start_col]
    match = FIELD_BEFORE_VALUE_PATTERN.search(prefix)
    if match:
        return match.group("field")
    return f"{service.upper()}_API_KEY"


def _structured_assignment_already_handles(line: str, value: str) -> bool:
    for pattern in STRUCTURED_ASSIGNMENT_PATTERNS:
        match = pattern.match(line)
        if not match:
            continue
        extracted = extract_assignment_value(match.group("key"), match.group("value"))
        if extracted == value:
            return True
    return False


def _local_url_for_match(text: str, start: int, end: int, service: str, default_url: str) -> str:
    context = text[max(0, start - 800) : min(len(text), end + 800)]
    return pick_domain(find_domains(context), service, default_url)


def collect_generic_key_candidates(text: str, relpath: str) -> list[dict]:
    candidates: list[dict] = []
    cursor = 0
    for line_no, raw_line in enumerate(text.splitlines(keepends=True), start=1):
        line_start = cursor
        line_end = cursor + len(raw_line)
        cursor = line_end
        line = raw_line.rstrip("\r\n")
        for service, default_url, pattern in GENERIC_API_KEY_PATTERNS:
            for match in pattern.finditer(line):
                value = match.group(0)
                if _structured_assignment_already_handles(line, value):
                    continue
                field = _field_before_match(line, match.start(), service)
                candidate = annotate_candidate(
                    {
                        "entry_type": "api_key",
                        "field": field,
                        "value": value,
                        "service": service,
                        "default_url": default_url,
                        "local_url": _local_url_for_match(
                            text,
                            line_start + match.start(),
                            min(line_end, line_start + match.end()),
                            service,
                            default_url,
                        ),
                        "source": f"{relpath} line {line_no}",
                        "env_name": field if ENV_NAME_PATTERN.fullmatch(field) else None,
                    },
                    relpath,
                    line=line,
                    match_start_col=match.start(),
                    match_end_col=match.end(),
                )
                if candidate is not None:
                    candidates.append(candidate)
    return candidates


__all__ = [
    "GENERIC_API_KEY_PATTERNS",
    "collect_generic_key_candidates",
]
