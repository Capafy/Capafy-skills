from __future__ import annotations

from typing import Iterable, Optional



SERVICE_HINTS = {
    "Anthropic": ("anthropic", "claude"),
    "OpenAI": ("openai",),
    "Google": ("google", "googleapis", "gemini"),
    "AWS": ("aws", "amazon"),
    "GitHub": ("github",),
    "Slack": ("slack",),
    "SendGrid": ("sendgrid",),
    "Stripe": ("stripe",),
    "Twilio": ("twilio",),
    "PyPI": ("pypi", "pythonhosted"),
    "npm": ("npmjs",),
    "MongoDB": ("mongodb", "mongo"),
    "Redis": ("redis",),
}


def pick_domain(domains: Iterable[str], service: str, default_url: str) -> str:
    domain_list = [domain for domain in domains if domain]
    if not domain_list:
        return default_url
    hints = SERVICE_HINTS.get(service, ())
    for domain in domain_list:
        lowered = domain.lower()
        if any(hint in lowered for hint in hints):
            return domain
    if default_url and default_url != "unknown":
        return default_url
    return domain_list[0]


def append_candidate(candidates: list[dict], candidate: Optional[dict]) -> None:
    if candidate is not None:
        candidates.append(candidate)


__all__ = ["append_candidate", "pick_domain"]
