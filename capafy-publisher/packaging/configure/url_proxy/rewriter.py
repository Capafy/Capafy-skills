from __future__ import annotations

from pathlib import Path
from typing import Any

from packaging._shared.config_files.dotenv import replace_dotenv_value_text
from packaging._shared.config_files.json_io import replace_json_value_text, upsert_json_value_file
from packaging._shared.config_files.toml_loader import replace_toml_value_text, upsert_toml_value_file
from packaging.configure.contracts import (
    PlanField,
    SourceKind,
    UrlProxyPair,
)


def apply_url_proxy_to_staging(
    staging_root: Path,
    pairs: list[UrlProxyPair],
    *,
    field_rewrite_hook: Any = None,
    finalize_hook: Any = None,
) -> None:
    for pair in pairs:
        for plan_field in (pair.key, pair.url):
            if field_rewrite_hook and field_rewrite_hook(staging_root, plan_field, pair):
                continue
            if plan_field.source_kind == SourceKind.FILE:
                _replace_in_file(staging_root, plan_field)
            elif plan_field.source_kind == SourceKind.SYNTHESIZED:
                _synthesize_in_file(staging_root, plan_field)

    if finalize_hook:
        finalize_hook(staging_root, pairs)


def _replace_in_file(staging_root: Path, plan_field: PlanField) -> None:
    if not plan_field.location or not plan_field.source_relpath:
        return
    file_path = staging_root / plan_field.source_relpath
    if not file_path.is_file():
        return

    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        return

    fmt = plan_field.location.fmt
    if fmt == "dotenv":
        original_value = str(plan_field.original_value or "").strip()
        if not original_value:
            return
        updated = replace_dotenv_value_text(
            text,
            expected_value=original_value,
            replacement=plan_field.placeholder,
            occurrence_index=plan_field.location.occurrence_index,
        )
    elif fmt == "json":
        if not plan_field.location.json_pointer:
            return
        updated = replace_json_value_text(text, plan_field.location.json_pointer, plan_field.placeholder)
    elif fmt == "toml":
        updated = replace_toml_value_text(
            text,
            section=plan_field.location.toml_section,
            field=plan_field.field,
            replacement=plan_field.placeholder,
        )
    else:
        return

    if updated != text:
        file_path.write_text(updated, encoding="utf-8")


def _synthesize_in_file(staging_root: Path, plan_field: PlanField) -> None:
    if not plan_field.source_relpath:
        return
    file_path = staging_root / plan_field.source_relpath
    if plan_field.location and plan_field.location.fmt == "toml":
        upsert_toml_value_file(
            file_path,
            section=plan_field.location.toml_section,
            field=plan_field.field,
            value=plan_field.placeholder,
        )
    elif plan_field.location and plan_field.location.fmt == "json":
        upsert_json_value_file(
            file_path,
            pointer=plan_field.location.json_pointer,
            field=plan_field.field,
            value=plan_field.placeholder,
        )


__all__ = ["apply_url_proxy_to_staging"]
