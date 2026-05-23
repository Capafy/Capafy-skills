from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
import re
import shutil
from pathlib import Path, PurePosixPath

from packaging._shared.common.fs import (
    is_within,
    windows_drive_mount_candidates as _windows_drive_mount_candidates,
    windows_path_parts as _windows_path_parts,
)
from packaging._shared.common.toml_loader import safe_toml_loads, tomllib
from packaging._shared.policies.path_refs import build_packaged_runtime_ref
from packaging.configure.selection.local_ref_confirmation import local_reference_should_be_staged
from packaging.configure.sensitive.literals import looks_like_platform_managed_placeholder_value


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
WINDOWS_DRIVE_PATH_PATTERN = re.compile(r"^(?P<drive>[A-Za-z]):[\\/](?P<rest>.*)$")

_LOCAL_PATH_PLACEHOLDER = "LOCAL_PATH_REDACTED"


def _safe_filename(path: Path, *, default: str) -> str:
    name = path.name.strip() or default
    return "".join(char if char.isalnum() or char in {".", "-", "_"} else "-" for char in name)


def _path_candidates(raw_value: str) -> list[Path]:
    candidates = [Path(raw_value).expanduser()]
    match = WINDOWS_DRIVE_PATH_PATTERN.match(raw_value.strip())
    if not match:
        return candidates

    parts = _windows_path_parts(match.group("rest"))
    for root in _windows_drive_mount_candidates(match.group("drive")):
        candidates.append(root.joinpath(*parts))
    return candidates


def _windows_user_home_candidates(raw_value: str) -> list[Path]:
    match = WINDOWS_DRIVE_PATH_PATTERN.match(raw_value.strip())
    if not match:
        return []
    parts = _windows_path_parts(match.group("rest"))
    if len(parts) < 2:
        return []
    if parts[0].lower() not in {"users", "documents and settings"}:
        return []
    home_value = f"{match.group('drive')}:{os.sep}{parts[0]}{os.sep}{parts[1]}"
    return _path_candidates(home_value)


def _allowed_roots(raw_value: str) -> list[Path]:
    roots = [Path.home()]
    try:
        roots.append(Path.home().expanduser().resolve())
    except OSError:
        pass
    userprofile = os.environ.get("USERPROFILE", "").strip()
    if userprofile:
        roots.extend(_path_candidates(userprofile))
    homedrive = os.environ.get("HOMEDRIVE", "").strip()
    homepath = os.environ.get("HOMEPATH", "").strip()
    if homedrive and homepath:
        roots.extend(_path_candidates(f"{homedrive}{homepath}"))
    roots.extend(_windows_user_home_candidates(raw_value))
    return roots


def _looks_like_platform_managed_placeholder(raw_value: str) -> bool:
    value = raw_value.strip()
    return value == _LOCAL_PATH_PLACEHOLDER or looks_like_platform_managed_placeholder_value(value)


def _looks_like_local_path(raw_value: str) -> bool:
    value = raw_value.strip()
    if not value:
        return False
    return (
        value.startswith(("~", "/", "./", "../", "\\\\"))
        or WINDOWS_DRIVE_PATH_PATTERN.match(value) is not None
    )


def _append_local_file_warning(
    warnings: list[dict] | None,
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


def _is_allowed_source_path(path: Path, raw_value: str) -> bool:
    resolved = path.resolve()
    for root in _allowed_roots(raw_value):
        try:
            resolved_root = root.expanduser().resolve()
        except OSError:
            continue
        if is_within(resolved, resolved_root):
            return True
    return False


def _parse_local_file_value(line: str, match: re.Match[str], field: CodexLocalFileField) -> str:
    try:
        payload = safe_toml_loads(line)
    except tomllib.TOMLDecodeError:
        return match.group("value")
    value = payload.get(field.name)
    if isinstance(value, str):
        return value
    return match.group("value")


def resolve_codex_local_config_file_source(raw_value: str) -> Path | None:
    for candidate in _path_candidates(raw_value):
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        if _is_allowed_source_path(resolved, raw_value):
            return resolved
    return None


def stage_codex_model_instructions_file(
    config_path: Path,
    staging_root: Path,
    *,
    stage_plan=None,
    warnings: list[dict] | None = None,
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
