from __future__ import annotations

import hashlib
import re
from pathlib import Path

from packaging.configure.sensitive.literals import infer_managed_value_type

PLATFORM_MANAGED_VALUE_PLACEHOLDER_PATTERN = re.compile(r"PLATFORM_MANAGED_VALUE_[A-Z0-9]{10}")
_SOURCE_FIELD_TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")


def _managed_value_placeholder_from_seed_parts(seed_parts: tuple[str, ...]) -> str:
    seed = "\n".join(part.strip() for part in seed_parts)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest().upper()[:10]
    return f"PLATFORM_MANAGED_VALUE_{digest}"


def split_source(source: str) -> tuple[str, str]:
    normalized = str(source or "").strip()
    if not normalized:
        return "", ""
    if " → " in normalized:
        path, detail = normalized.split(" → ", 1)
        return path.strip(), detail.strip()
    if " -> " in normalized:
        path, detail = normalized.split(" -> ", 1)
        return path.strip(), detail.strip()
    line_match = re.match(r"^(?P<path>.+?)\s+(?P<detail>line\s+\d+.*)$", normalized, flags=re.IGNORECASE)
    if line_match:
        return line_match.group("path").strip(), line_match.group("detail").strip()
    if "#" in normalized:
        path, detail = normalized.split("#", 1)
        return path.strip(), detail.strip()
    return normalized, ""


def build_placeholder(
    service: str,
    source: str,
    field: str = "",
    locator: str = "",
    value_type: str = "",
) -> str:
    return _managed_value_placeholder_from_seed_parts(
        (
            service,
            source,
            field,
            locator,
            value_type,
        )
    )


def build_redaction_placeholder(
    source: str,
    *,
    field: str = "",
    source_detail: str = "",
    value_type: str = "",
) -> str:
    return build_placeholder(
        "",
        source,
        field=field,
        locator=source_detail,
        value_type=value_type,
    )


def _redaction_value_type_variants_from_item(item: dict, field: str) -> list[str]:
    explicit_value_type = str(item.get("value_type") or "").strip()
    if explicit_value_type:
        return [explicit_value_type]
    inferred_value_type = infer_managed_value_type(field, str(item.get("value", "")))
    variants = [inferred_value_type] if inferred_value_type else []
    if "" not in variants:
        variants.append("")
    return variants


def build_redaction_placeholder_candidates(item: dict) -> list[str]:
    raw_source = str(item.get("source", "")).strip()
    source, source_detail_from_source = split_source(raw_source)
    item_source_detail = str(item.get("source_detail", "") or "").strip()
    source_detail = item_source_detail or source_detail_from_source
    field = str(item.get("field", "")).strip()
    value_types = _redaction_value_type_variants_from_item(item, field)

    placeholders: list[str] = []
    joined_sources: list[str] = []

    def append_placeholder(placeholder: str) -> None:
        if placeholder not in placeholders:
            placeholders.append(placeholder)

    def append_redaction_placeholder(
        source: str,
        *,
        field: str = "",
        source_detail: str = "",
        value_type: str = "",
    ) -> None:
        append_placeholder(
            build_redaction_placeholder(
                source,
                field=field,
                source_detail=source_detail,
                value_type=value_type,
            )
        )

    def append_joined_source(raw_source: str) -> None:
        normalized = str(raw_source or "").strip()
        if not normalized:
            return
        if normalized not in joined_sources:
            joined_sources.append(normalized)
        if "#" not in normalized:
            return

        base_source = normalized.split("#", 1)[0].strip()
        if base_source and base_source not in joined_sources:
            joined_sources.append(base_source)

    if source:
        canonical = source.strip()
        append_joined_source(canonical)
    field_aliases = item.get("field_aliases", [])
    normalized_fields: list[str] = []
    if isinstance(field_aliases, list):
        normalized_fields.extend(str(alias) for alias in field_aliases if alias)
    if field and field not in normalized_fields:
        normalized_fields.insert(0, field)

    for joined_source in joined_sources:
        alias_source, alias_detail = split_source(joined_source)
        effective_detail = source_detail or alias_detail
        for field_alias in normalized_fields:
            variants = [
                (field_alias, effective_detail),
                (field_alias, ""),
            ]
            for field_variant, detail_variant in variants:
                if not alias_source or (not field_variant and not detail_variant):
                    continue
                for value_type in value_types:
                    append_redaction_placeholder(
                        alias_source,
                        field=field_variant,
                        source_detail=detail_variant,
                        value_type=value_type,
                    )
        if alias_source and effective_detail:
            for value_type in value_types:
                append_redaction_placeholder(
                    alias_source,
                    field="",
                    source_detail=effective_detail,
                    value_type=value_type,
                )
    return placeholders


def _source_paths_from_item(item: dict) -> list[str]:
    result: list[str] = []

    def append_source_path(raw_source: str) -> None:
        normalized, _detail = split_source(str(raw_source).strip())
        if normalized and normalized not in result:
            result.append(normalized)
        if "#" not in normalized:
            return

        base_source = normalized.split("#", 1)[0].strip()
        if base_source and base_source not in result:
            result.append(base_source)

    source = str(item.get("source", "")).strip()
    append_source_path(source)
    return result


def _field_variants_from_item(item: dict) -> list[str]:
    result: list[str] = []
    field_aliases = item.get("field_aliases", [])
    if isinstance(field_aliases, list):
        for alias in field_aliases:
            normalized = str(alias).strip()
            if normalized and normalized not in result:
                result.append(normalized)

    field = str(item.get("field", "")).strip()
    if field and field not in result:
        result.insert(0, field)
    for alias in _infer_field_aliases_from_source_paths(item):
        if alias and alias not in result:
            result.append(alias)
    return result


def _infer_field_aliases_from_source_paths(item: dict) -> list[str]:
    result: list[str] = []
    source_detail = str(item.get("source_detail", "") or "").strip()
    if source_detail:
        tokens = _SOURCE_FIELD_TOKEN_PATTERN.findall(source_detail)
        if tokens:
            result.append(tokens[-1].strip())
    for source_path in _source_paths_from_item(item):
        if "#" not in source_path:
            continue
        fragment = source_path.split("#", 1)[1].strip()
        if not fragment:
            continue

        tokens = _SOURCE_FIELD_TOKEN_PATTERN.findall(fragment)
        if not tokens:
            continue
        alias = tokens[-1].strip()
        if alias and alias not in result:
            result.append(alias)
    return result


def _line_matches_field(line: str, field: str) -> bool:
    escaped = re.escape(field)
    return bool(
        re.match(rf'^\s*(?:export\s+)?{escaped}\s*=', line)
        or re.match(rf'^\s*["\']?{escaped}["\']?\s*:', line)
    )


def build_runtime_redaction_placeholder_candidates(
    item: dict,
    runtime_root: Path,
) -> list[str]:
    placeholders = build_redaction_placeholder_candidates(item)
    field_variants = _field_variants_from_item(item)
    if not field_variants:
        return placeholders

    value_types = _redaction_value_type_variants_from_item(item, field_variants[0])

    for source_path in _source_paths_from_item(item):
        for field_variant in field_variants:
            for value_type in value_types:
                placeholder = build_redaction_placeholder(
                    source_path,
                    field=field_variant,
                    source_detail="",
                    value_type=value_type,
                )
                if placeholder not in placeholders:
                    placeholders.append(placeholder)
        candidate_path = runtime_root / source_path
        if not candidate_path.is_file():
            continue
        try:
            lines = candidate_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue

        for line_no, line in enumerate(lines, start=1):
            for field_variant in field_variants:
                if not _line_matches_field(line, field_variant):
                    continue
                for value_type in value_types:
                    placeholder = build_redaction_placeholder(
                        source_path,
                        field=field_variant,
                        source_detail=f"line {line_no}",
                        value_type=value_type,
                    )
                    if placeholder not in placeholders:
                        placeholders.append(placeholder)
    return placeholders


__all__ = [
    "PLATFORM_MANAGED_VALUE_PLACEHOLDER_PATTERN",
    "build_placeholder",
    "build_redaction_placeholder",
    "build_redaction_placeholder_candidates",
    "build_runtime_redaction_placeholder_candidates",
    "split_source",
]
