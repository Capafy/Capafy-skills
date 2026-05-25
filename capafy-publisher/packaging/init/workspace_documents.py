from __future__ import annotations
from typing import Optional

import os
from pathlib import Path

from packaging._shared.common.fs import (
    display_stage_path,
    looks_like_absolute_symlink,
    looks_like_virtualenv_dir,
    read_text,
    relpath as fs_relpath,
)
from packaging._shared.common.packaged_files import should_skip_packaged_relpath
from packaging._shared.common.toml_loader import safe_toml_loads, tomllib
from packaging._shared.contracts.selectable import is_instruction_doc, should_skip_skill_reference_document
from packaging._shared.env_profiles.path_resolver import resolve_path_spec
from packaging.configure.selection.local_ref_confirmation import display_path_for_local_reference
from packaging.configure.selection.support import classify_selectable_directory
from packaging._shared.contracts.stage_plan import StagePlan, StageTreeSource

from .selection_candidates import SourceDocument


def _build_document_entry(display_path: str, source_file: Path, text: str) -> SourceDocument:
    return {
        "path": display_path,
        "text": text,
        "is_instruction": is_instruction_doc(display_path),
        "source_file": str(source_file),
    }


def _iter_tree_source_documents(
    tree_source: StageTreeSource,
    *,
    runtime_root: Optional[Path] = None,
    target=None,
) -> list[SourceDocument]:
    source_root = tree_source.source_root.expanduser().resolve(strict=False)
    if not source_root.is_dir():
        return []

    discovered: list[SourceDocument] = []
    seen: set[str] = set()

    for current, dirnames, filenames in os.walk(source_root, topdown=True):
        current_path = Path(current)
        current_relpath = fs_relpath(current_path, source_root)
        if source_root == runtime_root:
            dirnames[:] = []
        else:
            kept_dirs: list[str] = []

            for dirname in sorted(dirnames):
                candidate_path = current_path / dirname
                relpath = display_stage_path(current_relpath, dirname)
                display_path = display_stage_path(tree_source.display_prefix, relpath)
                selectable_path, _unit_type, keep_descending = classify_selectable_directory(
                    target,
                    candidate_path,
                    display_path,
                )


                if looks_like_virtualenv_dir(candidate_path):
                    continue
                if looks_like_absolute_symlink(candidate_path):
                    continue
                if should_skip_packaged_relpath(
                    relpath,
                    is_dir=True,
                    skip_skill_runtime_outputs=tree_source.skip_skill_runtime_outputs,
                    skill_runtime_prefixes=tree_source.skill_runtime_prefixes,
                    excluded_relpath_prefixes=tree_source.excluded_relpath_prefixes,
                ):
                    continue
                if keep_descending:
                    kept_dirs.append(dirname)

            dirnames[:] = kept_dirs

        for filename in sorted(filenames):
            source_file = current_path / filename
            relpath = display_stage_path(current_relpath, filename)
            display_path = display_stage_path(tree_source.display_prefix, relpath)
            if source_root == runtime_root and source_file.suffix.lower() not in (".md", ".txt"):
                continue
            if looks_like_absolute_symlink(source_file):
                continue
            if should_skip_packaged_relpath(
                relpath,
                is_dir=False,
                skip_skill_runtime_outputs=tree_source.skip_skill_runtime_outputs,
                skill_runtime_prefixes=tree_source.skill_runtime_prefixes,
                excluded_relpath_prefixes=tree_source.excluded_relpath_prefixes,
            ):
                continue
            if should_skip_skill_reference_document(display_path) or display_path in seen:
                continue

            text, _encoding = read_text(source_file)
            if text is None or not text.strip():
                continue
            discovered.append(_build_document_entry(display_path, source_file, text))
            seen.add(display_path)

    return discovered


def _iter_profile_fixed_instruction_documents(
    *,
    runtime_dir: Optional[str] = None,
    target=None,
) -> list[SourceDocument]:
    profile = getattr(target, "profile", None)
    if not isinstance(profile, dict):
        return []
    documents: list[SourceDocument] = []
    for file_spec in profile.get("fixed_scan_files", []):
        if not isinstance(file_spec, dict):
            continue
        display_path = str(file_spec.get("display_path", "") or "").strip().strip("/")
        if not display_path or not is_instruction_doc(display_path):
            continue
        if should_skip_skill_reference_document(display_path):
            continue
        source_file = resolve_path_spec(file_spec, runtime_dir=runtime_dir).expanduser()
        if not source_file.is_file():
            continue
        text, _encoding = read_text(source_file)
        if text is None or not text.strip():
            continue
        documents.append(_build_document_entry(display_path, source_file, text))
    return documents


def _source_file_for_display_path(stage_plan: StagePlan, display_path: str) -> Optional[Path]:
    normalized_display_path = display_path.strip().strip("/")
    if not normalized_display_path:
        return None
    for file_source in stage_plan.file_sources:
        if file_source.relative_target_path.as_posix() != normalized_display_path:
            continue
        source_file = file_source.source_file.expanduser()
        if source_file.is_file():
            return source_file
    return None


def _resolve_codex_model_instructions_source(raw_value: str) -> Optional[Path]:
    from packaging.configure.runtimes.codex.local_files import resolve_codex_local_config_file_source

    return resolve_codex_local_config_file_source(raw_value)


def _append_config_referenced_instruction_document(
    documents: list[SourceDocument],
    *,
    source_path: Optional[Path],
    stage_plan: StagePlan,
) -> None:
    if source_path is None or not source_path.is_file():
        return
    display_path = display_path_for_local_reference(source_path, stage_plan)
    if not display_path or not is_instruction_doc(display_path):
        return
    if should_skip_skill_reference_document(display_path):
        return
    text, _encoding = read_text(source_path)
    if text is None or not text.strip():
        return
    documents.append(_build_document_entry(display_path, source_path, text))


def _iter_codex_config_referenced_instruction_documents(stage_plan: StagePlan) -> list[SourceDocument]:
    config_path = _source_file_for_display_path(stage_plan, ".codex/config.toml")
    if config_path is None:
        return []
    text, _encoding = read_text(config_path)
    if text is None:
        return []
    try:
        payload = safe_toml_loads(text)
    except tomllib.TOMLDecodeError:
        return []
    raw_value = payload.get("model_instructions_file")
    if not isinstance(raw_value, str):
        return []

    documents: list[SourceDocument] = []


    _append_config_referenced_instruction_document(
        documents,
        source_path=_resolve_codex_model_instructions_source(raw_value),
        stage_plan=stage_plan,
    )
    return documents


def _iter_config_referenced_instruction_documents(stage_plan: StagePlan, *, target=None) -> list[SourceDocument]:
    env_id = str(getattr(target, "env_id", "") or "").strip()
    if env_id == "codex":
        return _iter_codex_config_referenced_instruction_documents(stage_plan)
    return []


def _append_unique_document(
    documents: list[SourceDocument],
    seen: set[str],
    document: SourceDocument,
) -> None:
    path = str(document.get("path", "")).strip()
    if not path or path in seen:
        return
    seen.add(path)
    documents.append(document)


def discover_documents(
    stage_plan: StagePlan,
    *,
    runtime_dir: Optional[str] = None,
    target=None,
) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    seen: set[str] = set()
    runtime_root = Path(runtime_dir).expanduser().resolve(strict=False) if runtime_dir else None

    for tree_source in stage_plan.tree_sources:
        for document in _iter_tree_source_documents(tree_source, runtime_root=runtime_root, target=target):
            _append_unique_document(documents, seen, document)

    for document in _iter_profile_fixed_instruction_documents(runtime_dir=runtime_dir, target=target):
        _append_unique_document(documents, seen, document)

    for document in _iter_config_referenced_instruction_documents(stage_plan, target=target):
        _append_unique_document(documents, seen, document)

    for file_source in stage_plan.file_sources:
        source_file = file_source.source_file.expanduser()
        relpath = str(file_source.relative_target_path.as_posix())
        display_path = str(file_source.source_key or "").strip() if file_source.scan_only else ""
        if not display_path:
            display_path = relpath
        if not source_file.is_file():
            continue
        if should_skip_skill_reference_document(display_path) or display_path in seen:
            continue
        text, _encoding = read_text(source_file)
        if text is None or not text.strip():
            continue
        _append_unique_document(documents, seen, _build_document_entry(display_path, source_file, text))

    documents.sort(key=lambda item: str(item.get("path", "")))
    return documents


__all__ = [
    "discover_documents",
]
