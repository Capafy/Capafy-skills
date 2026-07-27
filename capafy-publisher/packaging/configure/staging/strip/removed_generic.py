from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, TypedDict

from packaging._shared.common.fs import is_within
from packaging._shared.config_files.json_io import remove_json_file_object_key_containing_string
from packaging._shared.config_files.toml_loader import remove_toml_key_containing_value_text
from packaging._shared.config_files.yaml_loader import (
    remove_yaml_object_key_containing_string,
    safe_yaml_dumps,
    safe_yaml_loads,
)
from packaging._shared.config_files.dotenv import remove_dotenv_key_containing_value_text
from packaging.configure.staging.review_confirmation import (
    GenericIdentity,
    confirmed_generic_identities,
    generic_entry_identities,
)
from packaging.configure.staging.source_boundary import normalize_packaged_source_relpath


_JSON_SUFFIXES = {".json", ".jsonc"}
_YAML_SUFFIXES = {".yaml", ".yml"}
_TOML_SUFFIXES = {".toml"}


class RemovedGenericResult(TypedDict):
    reviewed_scan: dict[str, Any]
    summary: dict[str, int]


def _supported_source_format(source: str, source_detail: str) -> str:
    detail = str(source_detail or "").strip()
    if detail.startswith("json:"):
        return "json"
    if detail.startswith("yaml:"):
        return "yaml"
    if detail.startswith("toml:"):
        return "toml"

    suffix = Path(source).suffix.lower()
    name = Path(source).name
    if suffix in _JSON_SUFFIXES:
        return "json"
    if suffix in _YAML_SUFFIXES:
        return "yaml"
    if suffix in _TOML_SUFFIXES:
        return "toml"
    if name == ".env" or name.startswith(".env."):
        return "dotenv"
    return ""


def _safe_staging_file(staging_root: Path, source: object) -> tuple[str, Optional[Path]]:
    relpath = normalize_packaged_source_relpath(source)
    if not relpath:
        return "", None
    root = Path(staging_root).resolve(strict=False)
    candidate = (root / relpath).resolve(strict=False)
    if not is_within(candidate, root) or not candidate.is_file():
        return relpath, None
    return relpath, candidate


def _entry_placeholder(entry: dict[str, Any]) -> str:
    return str(entry.get("placeholder", "") or "").strip()


def _remove_json_entry(path: Path, entry: dict[str, Any]) -> bool:
    placeholder = _entry_placeholder(entry)
    if not placeholder:
        return False
    return remove_json_file_object_key_containing_string(path, placeholder)


def _remove_dotenv_entry(path: Path, entry: dict[str, Any]) -> bool:
    placeholder = _entry_placeholder(entry)
    if not placeholder:
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    updated, changed = remove_dotenv_key_containing_value_text(text, placeholder)
    if changed:
        path.write_text(updated, encoding="utf-8")
    return changed


def _remove_yaml_entry(path: Path, entry: dict[str, Any]) -> bool:
    placeholder = _entry_placeholder(entry)
    if not placeholder:
        return False
    try:
        payload = safe_yaml_loads(path.read_text(encoding="utf-8"))
    except (OSError, RuntimeError, ValueError):
        return False
    if not remove_yaml_object_key_containing_string(payload, placeholder):
        return False
    path.write_text(safe_yaml_dumps(payload), encoding="utf-8")
    return True


def _remove_toml_entry(path: Path, entry: dict[str, Any]) -> bool:
    placeholder = _entry_placeholder(entry)
    if not placeholder:
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    updated, changed = remove_toml_key_containing_value_text(text, placeholder)
    if changed:
        path.write_text(updated, encoding="utf-8")
    return changed


def _remove_supported_entry(staging_root: Path, entry: dict[str, Any]) -> bool:
    source, path = _safe_staging_file(staging_root, entry.get("source"))
    if path is None:
        return False
    fmt = _supported_source_format(source, str(entry.get("source_detail", "") or ""))
    if fmt == "json":
        return _remove_json_entry(path, entry)
    if fmt == "dotenv":
        return _remove_dotenv_entry(path, entry)
    if fmt == "yaml":
        return _remove_yaml_entry(path, entry)
    if fmt == "toml":
        return _remove_toml_entry(path, entry)
    return False


def remove_unconfirmed_generic_config_values(
    staging_root: Path,
    *,
    reviewed_scan: dict[str, Any],
    required_credentials_payload: dict[str, Any],
    baseline_reviewed_scan: Optional[dict[str, Any]] = None,
) -> RemovedGenericResult:
    baseline = baseline_reviewed_scan if isinstance(baseline_reviewed_scan, dict) else reviewed_scan
    generic = baseline.get("generic", [])
    if not isinstance(generic, list):
        return {"reviewed_scan": reviewed_scan, "summary": {"generic_config_entries_removed": 0}}

    confirmed = confirmed_generic_identities(required_credentials_payload)
    if confirmed is None:
        return {"reviewed_scan": reviewed_scan, "summary": {"generic_config_entries_removed": 0}}

    removed = 0
    removed_identities: set[GenericIdentity] = set()
    for entry in generic:
        if not isinstance(entry, dict):
            continue
        entry_identities = generic_entry_identities(entry)
        if not entry_identities or entry_identities & confirmed:
            continue
        if _remove_supported_entry(staging_root, entry):
            removed += 1
            removed_identities.update(entry_identities)

    updated_reviewed_scan = reviewed_scan
    current_generic = reviewed_scan.get("generic", [])
    if removed_identities and isinstance(current_generic, list):
        kept_generic = []
        for entry in current_generic:
            if isinstance(entry, dict) and (generic_entry_identities(entry) & removed_identities):
                continue
            kept_generic.append(entry)
        updated_reviewed_scan = dict(reviewed_scan)
        updated_reviewed_scan["generic"] = [dict(item) if isinstance(item, dict) else item for item in kept_generic]
    return {
        "reviewed_scan": updated_reviewed_scan,
        "summary": {"generic_config_entries_removed": removed},
    }


__all__ = [
    "RemovedGenericResult",
    "remove_unconfirmed_generic_config_values",
]
