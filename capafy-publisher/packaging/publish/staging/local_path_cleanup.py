from __future__ import annotations
from typing import Optional

import json
from pathlib import Path

from packaging.common.constants import WORKSPACE_DOCUMENTS_MANIFEST_NAME
from packaging.common.exclusion_rules import is_content_scan_text_file
from packaging.common.fs import is_archive_artifact, iter_workspace_files, read_text, relpath
from packaging.config.json_io import walk_json_strings
from packaging.publish.artifacts.bundle_context import BUNDLE_CONTEXT_NAME
from packaging.publish.staging.manifest import STAGE_MANIFEST_NAME
from packaging.publish.staging.local_path_sanitizer import rewrite_local_path_text


_STRUCTURED_STAGE_MANIFESTS = frozenset({
    BUNDLE_CONTEXT_NAME,
    WORKSPACE_DOCUMENTS_MANIFEST_NAME,
    "agent.runtime_dependencies.json",
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
    return is_content_scan_text_file(path)


def redact_main_tree_local_paths(
    staging_root: Path,
    *,
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
        if is_archive_artifact(path.name):
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
