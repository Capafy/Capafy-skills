from __future__ import annotations

from packaging._shared.common.url_values import normalize_http_url_candidate
from packaging._shared.openclaw.official_providers import OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME
from packaging.configure.candidate import Candidate
from packaging.configure.contracts import PlanField, SourceKind, UrlProxyPair
from packaging.configure.sensitive.placeholders import build_placeholder


_CONFIG_REL = ".openclaw/openclaw.json"
_CONTRACT_ID = "openclaw"


def pair_openclaw_provider_candidates(candidates: list[Candidate]) -> list[UrlProxyPair]:
    by_provider: dict[str, dict[str, list[Candidate]]] = {}
    for c in candidates:
        pname = c.extra.get("provider_name", "")
        if not pname:
            continue
        by_provider.setdefault(pname, {"keys": [], "urls": []})
        if c.role == "api_key":
            by_provider[pname]["keys"].append(c)
        elif c.role == "base_url":
            by_provider[pname]["urls"].append(c)

    pairs: list[UrlProxyPair] = []
    for provider_name, group in by_provider.items():
        keys = [
            candidate
            for candidate in group["keys"]
            if str(candidate.value or "").strip()
            or bool(candidate.extra.get("placeholder_provider"))
            or candidate.source_kind == SourceKind.SYNTHESIZED
        ]
        urls = group["urls"]
        if not keys:
            continue
        url_c = urls[0] if urls else None
        spec = OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME.get(provider_name)
        service = spec.service if spec else str(keys[0].extra.get("service", "") or provider_name)
        base_url = spec.base_url if spec else (url_c.value if url_c else "")
        if not normalize_http_url_candidate(base_url):
            continue
        if spec is None and url_c is None:
            continue
        model = _candidate_metadata(keys, urls, "model")
        api_format = _candidate_metadata(keys, urls, "api_format") or (spec.api if spec else "")
        if not api_format:
            raise ValueError(
                f"OpenClaw provider {provider_name} is missing api; "
                f"set models.providers.{provider_name}.api before publishing"
            )

        for idx, key_c in enumerate(keys):
            key_index = _candidate_key_index(key_c, idx)
            base_group = f"{_CONFIG_REL}#models.providers.{provider_name}"
            grp = base_group if key_index == 0 else f"{base_group}.apiKey[{key_index}]"
            placeholder_field = key_c.field if key_index == 0 else f"{key_c.field}[{key_index}]"
            key_ph = build_placeholder(
                service,
                _CONFIG_REL,
                field=placeholder_field,
                locator=base_url,
            )
            url_field = f"models.providers.{provider_name}.baseUrl"
            url_ph = build_placeholder(
                service,
                _CONFIG_REL,
                field=url_field,
                locator=base_url,
                value_type="url",
            )

            pairs.append(UrlProxyPair(
                contract_id=_CONTRACT_ID,
                service=service,
                group=grp,
                key=PlanField(
                    field=key_c.field,
                    service=service,
                    source_kind=key_c.source_kind,
                    source_relpath=_CONFIG_REL,
                    location=key_c.location,
                    original_value=key_c.value,
                    placeholder=key_ph,
                    reviewed_occurrence_index=key_index + 1,
                ),
                url=PlanField(
                    field=url_field,
                    service=service,
                    source_kind=SourceKind.FILE if url_c else SourceKind.SYNTHESIZED,
                    source_relpath=_CONFIG_REL,
                    location=url_c.location if url_c else None,
                    original_value=url_c.value if url_c else base_url,
                    placeholder=url_ph,
                ),
                is_synthesized=bool(key_c.extra.get("placeholder_provider")) or key_c.source_kind == SourceKind.SYNTHESIZED,
                model=model,
                api_format=api_format,
            ))

    return pairs


def _candidate_key_index(candidate: Candidate, fallback: int) -> int:
    raw = candidate.extra.get("key_index", fallback)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return fallback


def _candidate_metadata(
    keys: list[Candidate],
    urls: list[Candidate],
    field: str,
) -> str:
    for candidate in [*keys, *urls]:
        value = str(candidate.extra.get(field, "") or "").strip()
        if value:
            return value
    return ""


__all__ = ["pair_openclaw_provider_candidates"]
