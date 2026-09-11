from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional

from packaging.common.fs import is_archive_artifact, iter_workspace_files, read_text, relpath as fs_relpath
from packaging.publish.artifacts.bundle_context import (
    BUYOUT_FORBIDDEN_DIRS,
    BUYOUT_FORBIDDEN_FILES,
    validate_agent_type,
)
from packaging.publish.staging.manifest import STAGE_MANIFEST_NAME
from packaging.runtime import get_target

def _present_top_level_entries(runtime_root: Path) -> list[str]:
    return sorted(child.name for child in runtime_root.iterdir())


def _top_level_skill_directories(runtime_root: Path) -> list[Path]:
    return sorted(
        (child for child in runtime_root.iterdir() if child.is_dir()),
        key=lambda path: path.name,
    )


def _entry_attr_sources(entry: dict) -> list[dict]:
    sources = [entry]
    for child_key in ("url",):
        child = entry.get(child_key)
        if isinstance(child, dict):
            sources.append(child)
    return sources


def _entry_attr_values(entry: dict, attr_name: str) -> tuple[str, ...]:
    values: list[str] = []
    for index, source in enumerate(_entry_attr_sources(entry)):
        value = str(source.get(attr_name, "") or "").strip()
        unique = attr_name == "source" and index > 0
        if value and (not unique or value not in values):
            values.append(value)
    return tuple(values)


def _reviewed_scan_entry(entry: dict) -> dict:
    fields = _entry_attr_values(entry, "field")
    return {
        "field": fields[0] if fields else str(entry.get("use", "")).strip() or "unnamed_entry",
        "disposition": str(entry.get("final_disposition", "")).strip(),
        "values": _entry_attr_values(entry, "value"),
        "placeholders": _entry_attr_values(entry, "placeholder"),
        "source": _entry_attr_values(entry, "source"),
    }


def _iter_reviewed_scan_entries(reviewed_scan_payload: Optional[dict]) -> list[dict]:
    if not isinstance(reviewed_scan_payload, dict):
        return []
    items: list[dict] = []
    for bucket in ("url_proxy", "generic"):
        raw_items = reviewed_scan_payload.get(bucket, [])
        if not isinstance(raw_items, list):
            continue
        for entry in raw_items:
            if isinstance(entry, dict):
                items.append(_reviewed_scan_entry(entry))
    return items


def _collect_runtime_text(runtime_root: Path) -> str:
    chunks: list[str] = []
    for path in iter_workspace_files(runtime_root, skip_system=False):
        if is_archive_artifact(path.name):
            continue
        text, _encoding = read_text(path)
        if text is not None:
            chunks.append(text)
    return "\n".join(chunks)


def _validate_structure_check(runtime_root: Path) -> dict:
    top_level_entries = _present_top_level_entries(runtime_root)
    skill_directories = _top_level_skill_directories(runtime_root)
    missing_skill_md = [
        path.name
        for path in skill_directories
        if not (path / "SKILL.md").is_file()
    ]
    forbidden_dirs = [name for name in top_level_entries if name in BUYOUT_FORBIDDEN_DIRS]
    forbidden_paths: list[str] = []
    scan_only_residual: list[str] = []
    internal_manifest_residual: list[str] = []
    dependency_files: list[str] = []
    for path in iter_workspace_files(runtime_root, skip_system=False):
        relpath = fs_relpath(path, runtime_root)
        if path.name in BUYOUT_FORBIDDEN_FILES:
            forbidden_paths.append(relpath)
        if relpath == "_scan_only" or relpath.startswith("_scan_only/"):
            scan_only_residual.append(relpath)
        if relpath == STAGE_MANIFEST_NAME:
            internal_manifest_residual.append(relpath)
        if path.is_file() and path.name in {"requirements.txt", "package.json", "pyproject.toml"}:
            dependency_files.append(relpath)

    install_doc = (runtime_root / "INSTALL.md").is_file()
    ok = (
        bool(skill_directories)
        and not missing_skill_md
        and not forbidden_dirs
        and not forbidden_paths
        and not scan_only_residual
        and not internal_manifest_residual
    )
    return {
        "ok": ok,
        "skill_md_present": bool(skill_directories) and not missing_skill_md,
        "skill_directories": [path.name for path in skill_directories],
        "missing_skill_md": missing_skill_md,
        "install_md_present": install_doc,
        "top_level_entries": top_level_entries,
        "forbidden_dirs": forbidden_dirs,
        "forbidden_paths": forbidden_paths,
        "no_scan_only_residual": not scan_only_residual,
        "scan_only_residual": scan_only_residual,
        "no_internal_manifest_residual": not internal_manifest_residual,
        "internal_manifest_residual": internal_manifest_residual,
        "dependency_files": dependency_files,
    }


def _validate_disposition_consistency(runtime_root: Path, reviewed_scan_payload: Optional[dict]) -> dict:
    runtime_text = _collect_runtime_text(runtime_root)
    placeholder_to_disposition: list[dict] = []
    excluded_value_cleaned: list[dict] = []
    ok = True
    for item in _iter_reviewed_scan_entries(reviewed_scan_payload):
        field = item["field"]
        disposition = item["disposition"]
        if disposition == "replace_with_placeholder":
            for placeholder in item["placeholders"]:
                present = placeholder in runtime_text
                placeholder_to_disposition.append({"field": field, "placeholder": placeholder, "ok": present})
                if not present:
                    ok = False
        elif disposition == "exclude_value":
            for value in item["values"]:
                cleaned = value not in runtime_text
                excluded_value_cleaned.append({"field": field, "value": value, "ok": cleaned})
                if not cleaned:
                    ok = False
    return {
        "ok": ok,
        "placeholder_to_disposition": placeholder_to_disposition,
        "excluded_value_cleaned": excluded_value_cleaned,
    }


def validate_download_runtime(
    runtime_root: Path,
    *,
    reviewed_scan_payload: Optional[dict] = None,
) -> dict:
    checks: list[dict] = []
    errors: list[str] = []
    warnings: list[str] = []

    structure_check = _validate_structure_check(runtime_root)
    skill_directories = structure_check["skill_directories"]
    missing_skill_md = structure_check["missing_skill_md"]
    skill_entries_ok = bool(skill_directories) and not missing_skill_md
    checks.append(
        {
            "id": "download_skill_entry",
            "kind": "blocking",
            "ok": skill_entries_ok,
            "summary": (
                f"Found SKILL.md in {len(skill_directories)} skill directories"
                if skill_entries_ok
                else "One or more top-level skill directories are missing SKILL.md"
            ),
            "skill_directories": skill_directories,
            "missing_skill_md": missing_skill_md,
        }
    )
    if not skill_directories:
        errors.append("download packages must include at least one top-level skill directory")
    elif missing_skill_md:
        errors.append(
            "download skill directories must each include SKILL.md: "
            + ", ".join(missing_skill_md)
        )

    layout_ok = structure_check["ok"]
    checks.append(
        {
            "id": "download_layout",
            "kind": "blocking",
            "ok": layout_ok,
            "summary": "Download directory layout is valid" if layout_ok else "Download directory layout is invalid",
            "top_level_entries": structure_check["top_level_entries"],
            "forbidden_dirs": structure_check["forbidden_dirs"],
        }
    )
    if structure_check["forbidden_dirs"]:
        errors.append(f"Unexpected top-level directory in download package: {structure_check['forbidden_dirs'][0]}")

    forbidden_ok = not structure_check["forbidden_paths"]
    checks.append(
        {
            "id": "download_forbidden_runtime_files",
            "kind": "blocking",
            "ok": forbidden_ok,
            "summary": "No run-online-only files found" if forbidden_ok else "Run-online-only files are still present",
            "forbidden_paths": structure_check["forbidden_paths"],
        }
    )
    if structure_check["forbidden_paths"]:
        errors.append(f"Unexpected runtime file in download package: {structure_check['forbidden_paths'][0]}")

    dependency_files = structure_check["dependency_files"]
    checks.append(
        {
            "id": "download_dependency_files",
            "kind": "non_blocking",
            "ok": True,
            "summary": f"Found {len(dependency_files)} dependency file(s)",
            "dependency_files": dependency_files,
        }
    )

    if not dependency_files:
        warnings.append(
            "No dependency files were found in the selected skill directories; "
            "if these skills need extra dependencies, make sure their install instructions are complete"
        )

    consistency_check = _validate_disposition_consistency(runtime_root, reviewed_scan_payload)
    if not consistency_check.get("ok", False):
        errors.append("download runtime content is inconsistent with reviewed_scan dispositions")

    return {
        "ok": not errors,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "structure_check": structure_check,
        "consistency_check": consistency_check,
    }


def run_artifact_validate(
    *,
    staging_path: str,
    env_id: str,
    reviewed_scan: Optional[dict[str, Any]],
    agent_type: str,
) -> dict[str, Any]:
    staging_root = Path(staging_path)
    if not staging_root.is_dir():
        raise ValueError(f"validation staging directory does not exist: {staging_root}")

    resolved_agent_type = validate_agent_type(agent_type)
    target = get_target(env_id)
    with tempfile.TemporaryDirectory(prefix="developer-runtime-validate-") as tmpdir:
        runtime_root = Path(tmpdir) / "runtime"
        shutil.copytree(staging_root, runtime_root, symlinks=True)
        if resolved_agent_type == "run_online":
            validation_payload = target.validate_runtime(runtime_root)
        else:
            if not isinstance(reviewed_scan, dict):
                raise ValueError("download validation requires reviewed_scan")
            validation_payload = validate_download_runtime(
                runtime_root,
                reviewed_scan_payload=reviewed_scan,
            )

    return validation_payload


__all__ = ["run_artifact_validate", "validate_download_runtime"]
