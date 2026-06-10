from __future__ import annotations

from packaging._shared.common.url_values import normalize_http_url_candidate
from packaging.configure.candidate import Candidate
from packaging.configure.contracts import PlanField, SourceKind, UrlProxyPair
from packaging.configure.runtimes.hermes.provider_scan import CONFIG_REL
from packaging.configure.sensitive.placeholders import build_placeholder
from packaging.configure.url_proxy.pair_builder import (
    first_candidate_extra_value,
    usable_provider_key_candidates,
)


CONTRACT_ID = "hermes"


def pair_hermes_provider_candidates(candidates: list[Candidate]) -> list[UrlProxyPair]:
    by_group: dict[str, dict[str, list[Candidate]]] = {}
    for candidate in candidates:
        group_path = str(candidate.extra.get("group_path", "") or "").strip()
        if not group_path:
            continue
        group = by_group.setdefault(group_path, {"keys": [], "urls": [], "models": []})
        if candidate.role == "api_key":
            group["keys"].append(candidate)
        elif candidate.role == "base_url":
            group["urls"].append(candidate)
        elif candidate.role == "url_proxy_group":
            group["models"].append(candidate)

    pairs: list[UrlProxyPair] = []
    for group_path, group in by_group.items():
        keys = usable_provider_key_candidates(group["keys"])
        if not keys:
            continue
        key_candidate = keys[0]
        url_candidate = group["urls"][0] if group["urls"] else None
        provider_candidates = (key_candidate, url_candidate)
        base_url = first_candidate_extra_value(provider_candidates, "base_url")
        if not normalize_http_url_candidate(base_url):
            continue
        service = first_candidate_extra_value(provider_candidates, "service") or group_path
        provider_name = first_candidate_extra_value(provider_candidates, "provider_name")
        model_candidate = group["models"][0] if group["models"] else None
        model = (
            str(model_candidate.value or "").strip()
            if model_candidate is not None
            else first_candidate_extra_value(provider_candidates, "model")
        )
        api_format = first_candidate_extra_value(provider_candidates, "api_format")
        key_placeholder = build_placeholder(
            service,
            CONFIG_REL,
            field=key_candidate.field,
            locator=base_url,
        )
        url_field = url_candidate.field if url_candidate else f"{group_path}.base_url"
        url_placeholder = build_placeholder(
            service,
            CONFIG_REL,
            field=url_field,
            locator=base_url,
            value_type="url",
        )
        model_field = None
        if model_candidate is not None:
            model_field = PlanField(
                field=str(model_candidate.extra.get("model_field", "") or "model"),
                service=service,
                source_kind=SourceKind.FILE,
                source_relpath=CONFIG_REL,
                location=model_candidate.location,
                original_value=model_candidate.value,
                placeholder=build_placeholder(
                    service,
                    CONFIG_REL,
                    field=model_candidate.field,
                    locator=base_url,
                    value_type="model",
                ),
            )

        pairs.append(UrlProxyPair(
            contract_id=CONTRACT_ID,
            service=service,
            group=f"{CONFIG_REL}#{group_path}",
            key=PlanField(
                field=key_candidate.field,
                service=service,
                source_kind=key_candidate.source_kind,
                source_relpath=CONFIG_REL,
                location=key_candidate.location,
                original_value=key_candidate.value,
                placeholder=key_placeholder,
            ),
            url=PlanField(
                field=url_field,
                service=service,
                source_kind=SourceKind.FILE if url_candidate else SourceKind.SYNTHESIZED,
                source_relpath=CONFIG_REL,
                location=url_candidate.location if url_candidate else None,
                original_value=url_candidate.value if url_candidate else base_url,
                placeholder=url_placeholder,
            ),
            is_synthesized=bool(key_candidate.extra.get("placeholder_provider")),
            model=model,
            model_field=model_field,
            api_format=api_format,
            provider_name=provider_name,
        ))
    return pairs


__all__ = ["pair_hermes_provider_candidates"]
