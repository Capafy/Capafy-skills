from __future__ import annotations

import json
from pathlib import Path

from packaging._shared.common.fs import is_archive_artifact, iter_workspace_files, read_text, relpath as fs_relpath
from packaging._shared.contracts.bundle_context import (
    BUYOUT_FORBIDDEN_DIRS,
    BUYOUT_FORBIDDEN_FILES,
)
from packaging._shared.contracts.stage_manifest import STAGE_MANIFEST_NAME


def load_buyout_reviewed_scan_payload(
    *,
    reviewed_scan_json: str | None = None,
    reviewed_scan_file: str | None = None,
) -> dict | None:
    if reviewed_scan_json and reviewed_scan_file:
        raise ValueError("--reviewed-scan-json and --reviewed-scan-file cannot be passed together")
    if reviewed_scan_json:
        payload = json.loads(reviewed_scan_json)
        if not isinstance(payload, dict):
            raise ValueError("buyout reviewed_scan_json must be an object")
        return payload
    if reviewed_scan_file:
        reviewed_scan_path = Path(reviewed_scan_file)
        if not reviewed_scan_path.is_file():
            raise ValueError(f"buyout reviewed_scan_file does not exist: {reviewed_scan_path}")
        payload = json.loads(reviewed_scan_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("buyout reviewed_scan_file must contain a JSON object")
        return payload
    return None


def _present_top_level_entries(runtime_root: Path) -> list[str]:
    return sorted(child.name for child in runtime_root.iterdir())


def _entry_attr_sources(entry: dict) -> list[dict]:
    sources = [entry]
    for child_key in ("api_key", "url"):
        child = entry.get(child_key)
        if isinstance(child, dict):
            sources.append(child)
    return sources


def _entry_attr_values(entry: dict, attr_name: str) -> tuple[str, ...]:
    values: list[str] = []
    for index, source in enumerate(_entry_attr_sources(entry)):
        raw_values = [source.get(attr_name, "")]
        if not isinstance(raw_values, list):
            continue
        for raw_value in raw_values:
            value = str(raw_value or "").strip()
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


def _iter_reviewed_scan_entries(reviewed_scan_payload: dict | None) -> list[dict]:
    if not isinstance(reviewed_scan_payload, dict):
        return []
    items: list[dict] = []
    for bucket in ("url_proxy", "generic", "env_var"):
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

    bundled_skill = (runtime_root / "SKILL.md").is_file()
    install_doc = (runtime_root / "INSTALL.md").is_file()
    ok = (
        bundled_skill
        and not forbidden_dirs
        and not forbidden_paths
        and not scan_only_residual
        and not internal_manifest_residual
    )
    return {
        "ok": ok,
        "skill_md_present": bundled_skill,
        "install_md_present": install_doc,
        "top_level_entries": top_level_entries,
        "forbidden_dirs": forbidden_dirs,
        "forbidden_paths": forbidden_paths,
        "no_scan_only_residual": not scan_only_residual,
        "scan_only_residual": scan_only_residual,
        "no_internal_manifest_residual": not internal_manifest_residual,
        "internal_manifest_residual": internal_manifest_residual,
        "dependency_files": dependency_files,
        "no_dangling_remaps": True,
    }


def _validate_disposition_consistency(runtime_root: Path, reviewed_scan_payload: dict | None) -> dict:
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


def validate_buyout_runtime(
    runtime_root: Path,
    *,
    target_name: str,
    reviewed_scan_payload: dict | None = None,
) -> dict:
    checks: list[dict] = []
    errors: list[str] = []
    warnings: list[str] = []

    skill_md_exists = (runtime_root / "SKILL.md").is_file()
    checks.append(
        {
            "id": "buyout_skill_entry",
            "kind": "blocking",
            "ok": skill_md_exists,
            "summary": "Top-level SKILL.md found" if skill_md_exists else "Missing top-level SKILL.md",
        }
    )
    if not skill_md_exists:
        errors.append("buyout packages must include a top-level SKILL.md")

    structure_check = _validate_structure_check(runtime_root)
    layout_ok = structure_check["ok"]
    checks.append(
        {
            "id": "buyout_layout",
            "kind": "blocking",
            "ok": layout_ok,
            "summary": "Buyout directory layout is valid" if layout_ok else "Buyout directory layout is invalid",
            "top_level_entries": structure_check["top_level_entries"],
            "forbidden_dirs": structure_check["forbidden_dirs"],
        }
    )
    if structure_check["forbidden_dirs"]:
        errors.append(f"Unexpected top-level directory in buyout package: {structure_check['forbidden_dirs'][0]}")

    forbidden_ok = not structure_check["forbidden_paths"]
    checks.append(
        {
            "id": "buyout_forbidden_runtime_files",
            "kind": "blocking",
            "ok": forbidden_ok,
            "summary": "No cloud-runtime-only files found" if forbidden_ok else "Cloud-runtime-only files are still present",
            "forbidden_paths": structure_check["forbidden_paths"],
        }
    )
    if structure_check["forbidden_paths"]:
        errors.append(f"Unexpected runtime file in buyout package: {structure_check['forbidden_paths'][0]}")

    dependency_files = structure_check["dependency_files"]
    checks.append(
        {
            "id": "buyout_dependency_files",
            "kind": "non_blocking",
            "ok": True,
            "summary": f"Found {len(dependency_files)} dependency file(s)",
            "dependency_files": dependency_files,
        }
    )

    if not dependency_files:
        warnings.append("No top-level or component dependency files were found; if this skill needs extra dependencies, make sure the install instructions are complete")

    consistency_check = _validate_disposition_consistency(runtime_root, reviewed_scan_payload)
    if not consistency_check.get("ok", False):
        errors.append("buyout runtime content is inconsistent with reviewed_scan dispositions")

    return {
        "supported": True,
        "agent_type": "download",
        "ok": not errors,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "validation_mode": "buyout_skill_package_contract",
        "validation_target": target_name,
        "structure_check": structure_check,
        "consistency_check": consistency_check,
    }


def build_buyout_validation_payload(
    *,
    runtime_root: Path,
    resolved_target_name: str,
    reviewed_scan_payload: object,
) -> dict:
    return {
        "rehydration_supported": False,
        "deploy_items_count": None,
        "rehydration_source": None,
        "rehydrate_summary": None,
        **validate_buyout_runtime(
            runtime_root,
            target_name=resolved_target_name,
            reviewed_scan_payload=reviewed_scan_payload if isinstance(reviewed_scan_payload, dict) else None,
        ),
    }


__all__ = [
    "build_buyout_validation_payload",
    "load_buyout_reviewed_scan_payload",
    "validate_buyout_runtime",
]
