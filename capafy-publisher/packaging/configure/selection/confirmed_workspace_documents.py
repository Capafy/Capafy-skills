from __future__ import annotations
from typing import Optional

import json
from dataclasses import dataclass
from pathlib import Path

from packaging._shared.common.constants import WORKSPACE_DOCUMENTS_MANIFEST_NAME
from packaging._shared.common.fs import read_text
from packaging._shared.contracts.stage_plan import StageFileSource, StageTreeSource
from packaging._shared.contracts.selectable import is_absolute_like_path
from packaging._shared.contracts.selectable import is_instruction_doc, normalize_text
from .confirmed_outputs import (
    manifest_item,
    stage_sources_for_entry,
)
from .confirmed_payload import (
    CATEGORY_NAMES as _CATEGORY_NAMES,
    SELECTED_CATEGORIES as _SELECTED_CATEGORIES,
    load_confirmed_workspace_documents_payload,
    normalize_payload_categories,
)
from .confirmed_resolution import (
    packaged_path_for_entry,
    resolve_logical_source_path,
)
from .support import resolve_workspace_root


@dataclass(frozen=True)
class ConfirmedWorkspaceDocumentEntry:
    category: str
    logical_path: str
    source_path: Path
    packaged_path: str
    source_kind: str


def _entry_source_kind(source_path: Path, logical_path: str) -> str:
    if source_path.is_dir():
        return "directory"
    if source_path.is_file():
        return "file"
    raise ValueError(f"confirmed workspace document is neither a file nor a directory: {logical_path}")


def normalize_confirmed_workspace_document_entries(
    payload: dict,
    *,
    target_name: Optional[str],
    workspace: Optional[str],
    agent_type: str,
) -> dict[str, list[ConfirmedWorkspaceDocumentEntry]]:
    normalized_payload = normalize_payload_categories(payload)
    workspace_root = resolve_workspace_root(
        workspace=workspace,
        target_name=target_name,
    )
    excluded_paths = {
        normalize_text(item.get("path") if isinstance(item, dict) else item)
        for item in normalized_payload["excluded_sources"]
        if normalize_text(item.get("path") if isinstance(item, dict) else item)
    }
    used_packaged_paths: set[str] = set()
    entries: dict[str, list[ConfirmedWorkspaceDocumentEntry]] = {category: [] for category in _CATEGORY_NAMES}

    for category in _SELECTED_CATEGORIES:
        for raw_item in normalized_payload[category]:
            logical_path = normalize_text(raw_item.get("path") if isinstance(raw_item, dict) else raw_item)
            if not logical_path or logical_path in excluded_paths:
                continue
            source_path = resolve_logical_source_path(
                logical_path,
                workspace_root=workspace_root,
                target_name=target_name,
            )
            source_kind = _entry_source_kind(source_path, logical_path)
            if source_kind == "file" and is_instruction_doc(logical_path):
                text, _encoding = read_text(source_path)
                if text is not None and not text.strip():
                    continue
            packaged_path = packaged_path_for_entry(
                logical_path,
                source_path,
                target_name=target_name,
                agent_type=agent_type,
                used_paths=used_packaged_paths,
            )
            entries[category].append(
                ConfirmedWorkspaceDocumentEntry(
                    category=category,
                    logical_path=logical_path,
                    source_path=source_path,
                    packaged_path=packaged_path,
                    source_kind=source_kind,
                )
            )

    for raw_item in normalized_payload["excluded_sources"]:
        logical_path = normalize_text(raw_item.get("path") if isinstance(raw_item, dict) else raw_item)
        if not logical_path:
            continue
        try:
            source_path = resolve_logical_source_path(
                logical_path,
                workspace_root=workspace_root,
                target_name=target_name,
            )
            source_kind = "directory" if source_path.is_dir() else "file" if source_path.is_file() else "unknown"
        except ValueError:

            source_path = Path(logical_path)
            source_kind = "unknown"
        entries["excluded_sources"].append(
            ConfirmedWorkspaceDocumentEntry(
                category="excluded_sources",
                logical_path=logical_path,
                source_path=source_path,
                packaged_path="",
                source_kind=source_kind,
            )
        )

    return entries


def build_confirmed_workspace_document_stage_additions(
    *,
    skills_plan_json: Optional[str],
    target_name: Optional[str],
    workspace: Optional[str],
    agent_type: str,
) -> tuple[list[StageTreeSource], list[StageFileSource], Optional[dict]]:
    if agent_type == "download":
        return [], [], None

    payload = load_confirmed_workspace_documents_payload(
        skills_plan_json=skills_plan_json,
    )

    entries = normalize_confirmed_workspace_document_entries(
        payload,
        target_name=target_name,
        workspace=workspace,
        agent_type=agent_type,
    )
    if not any(entries[category] for category in ("workspace_documents", "excluded_sources")):
        return [], [], None

    tree_sources: list[StageTreeSource] = []
    file_sources: list[StageFileSource] = []
    for entry in entries["workspace_documents"]:
        tree_source, file_source = stage_sources_for_entry(entry)
        if tree_source is not None:
            tree_sources.append(tree_source)
        if file_source is not None:
            file_sources.append(file_source)

    manifest_payload = {
        "agent_type": agent_type,
        "workspace_documents": [
            manifest_item(
                item,
                preserve_logical_path=True,
                packaged=agent_type != "download",
            )
            for item in entries["workspace_documents"]
        ],
        "excluded_sources": [
            manifest_item(item, preserve_logical_path=True, packaged=False)
            for item in entries["excluded_sources"]
        ],
    }
    return tree_sources, file_sources, manifest_payload


def write_confirmed_workspace_documents_manifest(staging_root: Path, payload: Optional[dict]) -> Optional[Path]:
    if not payload:
        return None
    output_path = staging_root / WORKSPACE_DOCUMENTS_MANIFEST_NAME
    output_path.write_text(
        json.dumps(_public_manifest_payload(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def _public_manifest_payload(payload: dict) -> dict:
    public_payload = dict(payload)
    for key in ("workspace_documents", "excluded_sources"):
        items = payload.get(key)
        if not isinstance(items, list):
            continue
        public_items: list[dict] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            public_item = dict(item)
            logical_path = str(public_item.get("logical_path", "") or "").strip()
            if logical_path and not is_absolute_like_path(logical_path):
                public_item["source_path"] = logical_path
            else:
                public_item.pop("source_path", None)
            public_item.pop("resolved_source_path", None)
            public_item.pop("source_root", None)
            public_items.append(public_item)
        public_payload[key] = public_items
    return public_payload


__all__ = [
    "ConfirmedWorkspaceDocumentEntry",
    "build_confirmed_workspace_document_stage_additions",
    "load_confirmed_workspace_documents_payload",
    "normalize_confirmed_workspace_document_entries",
    "write_confirmed_workspace_documents_manifest",
]
