from __future__ import annotations
from typing import Optional

import json
from pathlib import Path

from packaging._shared.common.constants import WORKSPACE_DOCUMENTS_MANIFEST_NAME
from packaging._shared.common.fs import is_archive_artifact, iter_workspace_files, read_text, relpath
from packaging._shared.common.json_walk import walk_json_strings
from packaging._shared.contracts.bundle_context import BUNDLE_CONTEXT_NAME
from packaging._shared.contracts.stage_manifest import STAGE_MANIFEST_NAME
from packaging._shared.policies.content_scan import should_skip_local_path_cleanup_for_file
from packaging._shared.policies.local_path_sanitizer import rewrite_local_path_text
from packaging._shared.policies.text_files import TEXT_FILE_BASENAMES, TEXT_FILE_SUFFIXES
from packaging.configure.scan.platform_contracts import is_platform_contract_file


_STRUCTURED_STAGE_MANIFESTS = frozenset({
    BUNDLE_CONTEXT_NAME,
    WORKSPACE_DOCUMENTS_MANIFEST_NAME,
    "agent.runtime_dependencies.json",
    "agent.runtime_environment.json",
    "agent.selected_units.json",
})


def _redact_manifest_value(value: str, *, packaged_path_refs: dict[str, str]) -> tuple[str, int]:
    normalized = str(value or "").strip()
    if not normalized:
        return value, 0
    return rewrite_local_path_text(value, packaged_path_refs=packaged_path_refs)


def _redact_manifest_node(node: object, *, packaged_path_refs: dict[str, str]) -> tuple[object, int]:
    def redact_value(value: str, _key_name: Optional[str]) -> tuple[str, int]:
        return _redact_manifest_value(value, packaged_path_refs=packaged_path_refs)

    return walk_json_strings(node, redact_value)


def _redact_structured_stage_manifest(path: Path, *, packaged_path_refs: dict[str, str]) -> int:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    updated, redactions = _redact_manifest_node(payload, packaged_path_refs=packaged_path_refs)
    if redactions:
        path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return redactions


def _should_redact_main_tree_file(path: Path) -> bool:
    basename = path.name
    if should_skip_local_path_cleanup_for_file(basename):
        return False
    if basename in TEXT_FILE_BASENAMES or basename.startswith(".env"):
        return True
    return path.suffix.lower() in TEXT_FILE_SUFFIXES


def redact_main_tree_local_paths(
    staging_root: Path,
    *,
    target_name: Optional[str] = None,
    packaged_path_refs: dict[str, str],
) -> dict[str, int]:
    processed_files = 0
    total_replacements = 0
    known_refs = dict(packaged_path_refs)

    for path in iter_workspace_files(staging_root, skip_system=False):
        relative_file = relpath(path, staging_root)
        normalized = relative_file.replace("\\", "/")
        if not normalized or normalized == STAGE_MANIFEST_NAME or normalized.startswith("_scan_only/"):
            continue
        if is_archive_artifact(path.name) or is_platform_contract_file(normalized, target_name=target_name):
            continue
        if not _should_redact_main_tree_file(path):
            continue

        if normalized in _STRUCTURED_STAGE_MANIFESTS:
            replacements = _redact_structured_stage_manifest(path, packaged_path_refs=known_refs)
            if replacements:
                processed_files += 1
                total_replacements += replacements
            continue

        text, encoding = read_text(path)
        if text is None or encoding is None:
            continue
        updated, replacements = rewrite_local_path_text(text, packaged_path_refs=known_refs, source_path=path)
        if not replacements or updated == text:
            continue
        path.write_text(updated, encoding=encoding)
        processed_files += 1
        total_replacements += replacements

    return {
        "processed_file_count": processed_files,
        "total_replacements": total_replacements,
    }


__all__ = ["redact_main_tree_local_paths"]
