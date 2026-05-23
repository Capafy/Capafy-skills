from __future__ import annotations

from pathlib import PurePosixPath
from typing import TypedDict

from packaging._shared.contracts.path_shapes import basic_owning_selectable_paths
from packaging._shared.contracts.selection_groups import (
    RUNTIME_SELECTION_GROUP_KEYS,
    build_selected_selection_groups,
    strip_default_selection_fields,
)
from packaging._shared.contracts.selectable import normalize_text
from packaging._shared.contracts.path_shapes import is_cron_unit_type, is_plugin_unit_type
from packaging._shared.runtimes.contracts import call_optional_target_hook


class SourceDocument(TypedDict):

    path: str
    text: str
    is_instruction: bool
    source_file: str


class DiscoveryUnit(TypedDict, total=False):

    path: str
    name: str
    description: str
    synopsis: str
    source_root: str
    discovery_root: str
    unit_type: str
    has_primary_doc: bool
    has_skill_md: bool
    file_count: int
    size_bytes: int
    suspicious_reasons: list[str]
    structural_reasons: list[str]
    source_kind: str
    origin: str
    origin_ref: str
    id: str
    schedule: dict[str, str]
    payload: dict[str, str]
    reasons: list[str]


def _candidate_unit_is_supported(entry: DiscoveryUnit, *, target=None) -> bool:
    unit_type = str(entry.get("unit_type", "")).strip()
    if is_plugin_unit_type(unit_type) or is_cron_unit_type(unit_type):
        return bool(call_optional_target_hook(target, "allows_bundle_units", default=False))
    return True


def _owning_selectable_paths(path: str, *, target=None) -> tuple[str, ...]:
    return tuple(
        str(item).strip()
        for item in call_optional_target_hook(
            target,
            "owning_selectable_paths",
            path,
            default=basic_owning_selectable_paths(path),
        )
        if str(item).strip()
    )


def _is_under_skill_root(path: str) -> bool:
    parts = [part for part in PurePosixPath(path.rstrip("/")).parts if part and part != "."]
    return "skills" in parts


def _workspace_document_candidates(documents: list[SourceDocument], *, target=None) -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()
    for document in documents:
        if not bool(document.get("is_instruction", False)):
            continue
        path = normalize_text(document.get("path"))
        if not path or path == "_scan_only" or path.startswith("_scan_only/"):
            continue
        if _is_under_skill_root(path):
            continue
        if _owning_selectable_paths(path, target=target):
            continue
        if path in seen:
            continue
        items.append(
            {
                "path": path,
                "origin": "discovered_document",
                "source_kind": "workspace_document",
            },
        )
        seen.add(path)
    return items


def candidate_context_input(
    documents: list[SourceDocument],
    *,
    target=None,
) -> dict[str, list[dict]]:
    workspace_documents = _workspace_document_candidates(documents, target=target)
    return {
        "workspace_documents": workspace_documents,
    }


def candidate_selection_groups(
    candidate_units: list[DiscoveryUnit],
    *,
    target=None,
) -> dict[str, list[dict]]:
    supported_units = []
    for item in candidate_units:
        if not _candidate_unit_is_supported(item, target=target):
            continue
        supported_units.append(dict(item))
    groups = build_selected_selection_groups(
        selected_units=supported_units,
    )
    stripped_groups = strip_default_selection_fields(groups)
    return {key: stripped_groups.get(key, []) for key in RUNTIME_SELECTION_GROUP_KEYS}


__all__ = [
    "candidate_context_input",
    "candidate_selection_groups",
]
