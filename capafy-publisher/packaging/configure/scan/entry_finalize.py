from __future__ import annotations

from packaging.configure.sensitive.placeholders import build_placeholder


def entry_source_seed(entry: dict) -> str:
    return str(entry.get("_source_seed") or str(entry.get("source", "")).strip())


def entry_field_aliases(entry: dict) -> list[str]:
    aliases = entry.get("_field_aliases", [])
    if not isinstance(aliases, list):
        aliases = []
    field = str(entry.get("field", "")).strip()
    result: list[str] = []
    for alias in [field, *[str(item) for item in aliases if item]]:
        normalized = alias.strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def entry_source(entry: dict) -> str:
    return str(entry.get("source", "")).strip()


def finalize_entry(entry: dict) -> dict:
    final = dict(entry)
    final["placeholder"] = build_placeholder(
        final["service"],
        _placeholder_source(final),
        field=_placeholder_field(final),
        locator=final["url"],
        value_type=str(final.get("value_type", "")),
    )

    final.pop("_source_seed", None)
    final.pop("_placeholder_field", None)
    return final


def _placeholder_source(entry: dict) -> str:
    source = entry_source_seed(entry)
    detail = str(entry.get("source_detail", "") or "").strip()
    occurrence = str(entry.get("occurrence_index", "") or "").strip()
    return "\n".join((source, detail, occurrence))


def _placeholder_field(entry: dict) -> str:
    field = str(entry.get("field", "")).strip()
    occurrence = str(entry.get("_placeholder_field", "") or entry.get("occurrence_id", "")).strip()
    if not occurrence:
        return field
    return f"{field}#{occurrence}" if field else occurrence


def resolve_candidate_url(
    candidate: dict,
    env_url_hints: dict[str, str],
    service_url_hints: dict[str, str],
    value_url_hints: dict[str, str],
) -> str:
    value = candidate["value"]
    default_url = candidate["default_url"]
    url = candidate["local_url"]
    env_name = candidate["env_name"]

    if value in value_url_hints:
        return value_url_hints[value]

    if env_name and env_name in env_url_hints:
        return env_url_hints[env_name]

    service_name = candidate["service"].lower()
    return service_url_hints.get(service_name, url or default_url)


__all__ = [
    "entry_source",
    "finalize_entry",
    "resolve_candidate_url",
]
