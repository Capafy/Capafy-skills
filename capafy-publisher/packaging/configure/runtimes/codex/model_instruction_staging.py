from __future__ import annotations
from typing import Optional

from dataclasses import dataclass
import hashlib
import re
import shutil
from pathlib import Path, PurePosixPath

from packaging._shared.codex.local_files import (
    allowed_roots as _allowed_roots,
    looks_like_local_path as _looks_like_local_path,
    looks_like_platform_managed_placeholder as _looks_like_platform_managed_placeholder,
    parse_toml_local_file_value as _parse_toml_local_file_value,
    resolve_codex_local_config_file_source_with_roots as _resolve_codex_local_config_file_source_with_roots,
)
from packaging._shared.policies.path_refs import build_packaged_runtime_ref
from packaging._shared.selection.local_ref_confirmation import local_reference_should_be_staged


@dataclass(frozen=True)
class CodexLocalFileField:
    name: str
    target_dir: PurePosixPath
    default_filename: str
    warning_prefix: str


LOCAL_FILE_FIELDS = {
    "model_instructions_file": CodexLocalFileField(
        name="model_instructions_file",
        target_dir=PurePosixPath(".codex") / "model-instructions",
        default_filename="instructions.md",
        warning_prefix="codex_model_instructions",
    ),
    "model_catalog_json": CodexLocalFileField(
        name="model_catalog_json",
        target_dir=PurePosixPath(".codex") / "model-catalogs",
        default_filename="models.json",
        warning_prefix="codex_model_catalog",
    ),
}
LOCAL_FILE_FIELD_PATTERN = re.compile(
    r'^(?P<prefix>\s*(?P<field>model_instructions_file|model_catalog_json)\s*=\s*)'
    r'(?P<quote>["\'])(?P<value>.*?)(?P=quote)(?P<suffix>\s*(?:#.*)?)$'
)


def _safe_filename(path: Path, *, default: str) -> str:
    name = path.name.strip() or default
    return "".join(char if char.isalnum() or char in {".", "-", "_"} else "-" for char in name)


def _append_local_file_warning(
    warnings: Optional[list[dict]],
    *,
    field: CodexLocalFileField,
    code: str,
    raw_value: str,
) -> None:
    if warnings is None:
        return
    warnings.append(
        {
            "id": code,
            "severity": "warning",
            "field": field.name,
            "value": raw_value,
        }
    )


def _parse_local_file_value(line: str, match: re.Match[str], field: CodexLocalFileField) -> str:
    return _parse_toml_local_file_value(line, field.name, match.group("value"))


def resolve_codex_local_config_file_source(raw_value: str) -> Optional[Path]:
    return _resolve_codex_local_config_file_source_with_roots(raw_value, _allowed_roots(raw_value))


def stage_codex_model_instructions_file(
    config_path: Path,
    staging_root: Path,
    *,
    stage_plan=None,
    warnings: Optional[list[dict]] = None,
) -> int:
    text = config_path.read_text(encoding="utf-8")
    staged_count = 0
    changed = False
    updated_lines: list[str] = []

    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        newline = raw_line[len(line) :]
        match = LOCAL_FILE_FIELD_PATTERN.match(line)
        if not match:
            updated_lines.append(raw_line)
            continue

        field = LOCAL_FILE_FIELDS[match.group("field")]
        raw_value = _parse_local_file_value(line, match, field)
        if _looks_like_platform_managed_placeholder(raw_value):
            _append_local_file_warning(
                warnings,
                field=field,
                code=f"{field.warning_prefix}_placeholder_removed",
                raw_value=raw_value,
            )
            changed = True
            continue
        source_path = resolve_codex_local_config_file_source(raw_value)
        if source_path is None:
            if _looks_like_local_path(raw_value):
                _append_local_file_warning(
                    warnings,
                    field=field,
                    code=f"{field.warning_prefix}_source_unavailable",
                    raw_value=raw_value,
                )
                changed = True
                continue
            updated_lines.append(raw_line)
            continue

        if field.name == "model_instructions_file" and not local_reference_should_be_staged(source_path, stage_plan):
            _append_local_file_warning(
                warnings,
                field=field,
                code=f"{field.warning_prefix}_not_selected",
                raw_value=raw_value,
            )
            changed = True
            continue

        digest = hashlib.sha1(str(source_path).encode("utf-8")).hexdigest()[:10]
        target_rel = field.target_dir / f"{digest}-{_safe_filename(source_path, default=field.default_filename)}"
        target_path = staging_root / target_rel
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)

        quote = match.group("quote")
        runtime_ref = build_packaged_runtime_ref(target_rel.as_posix())
        updated_lines.append(
            f"{match.group('prefix')}{quote}{runtime_ref}{quote}{match.group('suffix')}{newline}"
        )
        staged_count += 1
        changed = True

    if changed:
        config_path.write_text("".join(updated_lines), encoding="utf-8")
    return staged_count


__all__ = ["resolve_codex_local_config_file_source", "stage_codex_model_instructions_file"]
