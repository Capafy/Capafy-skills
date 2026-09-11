from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Optional

from packaging.common.fs import relpath as fs_relpath
from packaging.common.packaged_files import iter_packaged_files
from packaging.publish.selection.selectable import (
    candidate_path_for_logical_path as _candidate_path_for_logical_path,
    validate_logical_path,
)
from packaging.runtime.stage_plan import StagePlan, StageTreeSource
from packaging.runtime.contracts import call_optional_target_hook
from packaging.publish.selection.units import infer_selection_unit_type


def load_external_skill_sources_payload(
    *,
    skills_plan_json: Optional[str],
) -> list[dict]:
    if not skills_plan_json:
        return []
    try:
        payload = json.loads(skills_plan_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"selected skills JSON parse failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("selected skills JSON top-level value must be an object")

    raw_groups = payload.get("selection_groups")
    raw_skills = raw_groups.get("skills", []) if isinstance(raw_groups, dict) else []
    if not isinstance(raw_skills, list):
        return []

    normalized: list[dict] = []
    seen: set[str] = set()
    for raw_item in raw_skills:
        if not isinstance(raw_item, dict):
            continue
        source_path = str(raw_item.get("source_path", "")).strip()
        if not source_path or str(raw_item.get("binding_kind", "")).strip() != "external_skill_dir":
            continue
        logical_path = PurePosixPath(
            validate_logical_path(
                raw_item.get("logical_path") or raw_item.get("path"),
                label="selection_groups.skills item path",
            ).rstrip("/")
        ).as_posix()
        unit_type = str(raw_item.get("unit_type", "skill")).strip() or "skill"
        if not logical_path:
            raise ValueError(
                "selection_groups.skills items with source_path must include path and source_path"
            )
        if unit_type != "skill":
            raise ValueError("selection_groups.skills item unit_type must be skill")
        if logical_path in seen:
            continue
        seen.add(logical_path)
        normalized.append(
            {
                "logical_path": logical_path,
                "source_path": source_path,
                "binding_kind": "external_skill_dir",
                "unit_type": unit_type,
                "origin": str(raw_item.get("origin") or "").strip(),
                "origin_ref": str(raw_item.get("origin_ref") or "").strip(),
                "snapshot_digest": str(raw_item.get("snapshot_digest") or "").strip(),
                "source_kind": str(raw_item.get("source_kind") or "").strip(),
                "skip_skill_runtime_outputs": raw_item.get("skip_skill_runtime_outputs"),
            }
        )
    return normalized


def compute_skill_snapshot_digest(skill_root: Path) -> str:
    root = skill_root.expanduser().resolve()
    digest = hashlib.sha256()
    for path in iter_packaged_files(
        root,
        skip_skill_runtime_outputs=True,
    ):
        relpath = fs_relpath(path, root)
        digest.update(relpath.encode("utf-8"))
        digest.update(b"\0")
        try:
            raw = path.read_bytes()
        except OSError:
            raw = b""
        digest.update(hashlib.sha256(raw).digest())
        digest.update(b"\0")
    return digest.hexdigest()


@dataclass(frozen=True)
class SelectedExternalSkillBinding:
    logical_path: str
    source_path: Path
    skip_skill_runtime_outputs: bool = True


_SKILL_SNAPSHOT_DIGESTS_BY_PATH: dict[str, str] = {}


def _safe_is_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


def _safe_is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _is_skill_dir(path: Path) -> bool:
    return _safe_is_dir(path) and _safe_is_file(path / "SKILL.md")


def _infer_unit_type(path: str, *, target=None) -> str:
    normalized = PurePosixPath(path.rstrip("/")).as_posix()
    return infer_selection_unit_type(normalized, target=target)


def _selected_skill_logical_paths(
    selected_skill_paths: Optional[set[str]],
    *,
    target=None,
) -> list[str]:
    if not selected_skill_paths:
        return []
    return [
        logical_path
        for logical_path in sorted(PurePosixPath(path.rstrip("/")).as_posix() for path in selected_skill_paths)
        if _infer_unit_type(logical_path, target=target) == "skill"
    ]


def _skill_resolves_from_tree_sources(
    tree_sources: list[StageTreeSource],
    logical_path: str,
) -> bool:
    for tree_source in tree_sources:
        candidate = _candidate_path_for_logical_path(
            tree_source.source_root.expanduser(),
            tree_source.display_prefix,
            logical_path,
        )
        if candidate is None:
            continue
        if _is_skill_dir(candidate):
            return True
    return False


def _missing_external_skill_sources_message(unresolved_paths: list[str]) -> str:
    sample = ", ".join(unresolved_paths[:3])
    extra_count = len(unresolved_paths) - 3
    suffix = f" (+{extra_count} more)" if extra_count > 0 else ""
    return (
        "selected skill paths could not be resolved from the current workspace or selection_groups.skills[].source_path: "
        f"{sample}{suffix}; rerun the upstream selection confirmation step and regenerate confirmed selections with "
        "selection_groups.skills[].source_path. Local scan/stage no longer rebuild these sources automatically."
    )


def _invalid_external_skill_source_message(logical_path: str, detail: str) -> str:
    return (
        f"selection_groups.skills source_path for selected skill {logical_path} {detail}; rerun the upstream selection confirmation "
        "step and regenerate confirmed selections"
    )


def selected_external_skill_bindings(
    tree_sources: list[StageTreeSource],
    *,
    selected_skill_paths: Optional[set[str]],
    skills_plan_json: Optional[str],
    target=None,
) -> list[SelectedExternalSkillBinding]:
    selected_logical_paths = _selected_skill_logical_paths(
        selected_skill_paths,
        target=target,
    )
    if not selected_logical_paths:
        return []

    payload_sources = load_external_skill_sources_payload(
        skills_plan_json=skills_plan_json,
    )
    payload_sources_by_path = {str(item["logical_path"]): item for item in payload_sources}

    selected_sources: list[SelectedExternalSkillBinding] = []
    unresolved_paths: list[str] = []
    for logical_path in selected_logical_paths:
        binding = payload_sources_by_path.get(logical_path)
        if binding is None:
            if _skill_resolves_from_tree_sources(tree_sources, logical_path):
                continue
            unresolved_paths.append(logical_path)
            continue

        source_path = Path(str(binding["source_path"])).expanduser()
        if not source_path.is_absolute():
            raise ValueError(
                _invalid_external_skill_source_message(logical_path, f"source_path must be an absolute path: {source_path}")
            )
        try:
            resolved = source_path.resolve(strict=True)
        except FileNotFoundError as exc:
            raise ValueError(
                _invalid_external_skill_source_message(logical_path, f"points to a missing path: {source_path}")
            ) from exc
        if not resolved.is_dir():
            raise ValueError(
                _invalid_external_skill_source_message(logical_path, f"does not point to a directory: {resolved}")
            )
        if not _is_skill_dir(resolved):
            raise ValueError(
                _invalid_external_skill_source_message(logical_path, f"does not contain SKILL.md: {resolved}")
            )
        expected_snapshot_digest = str(binding.get("snapshot_digest", "")).strip()
        if expected_snapshot_digest:
            digest_cache_key = str(resolved)

            if digest_cache_key not in _SKILL_SNAPSHOT_DIGESTS_BY_PATH:
                _SKILL_SNAPSHOT_DIGESTS_BY_PATH[digest_cache_key] = compute_skill_snapshot_digest(resolved)
            current_snapshot_digest = _SKILL_SNAPSHOT_DIGESTS_BY_PATH[digest_cache_key]
            if current_snapshot_digest != expected_snapshot_digest:
                raise ValueError(
                    _invalid_external_skill_source_message(
                        logical_path,
                        (
                            "snapshot digest changed: "
                            f"expected {expected_snapshot_digest}, got {current_snapshot_digest}"
                        ),
                    )
                )
        selected_sources.append(
            SelectedExternalSkillBinding(
                logical_path=logical_path,
                source_path=resolved,
                skip_skill_runtime_outputs=(
                    binding.get("skip_skill_runtime_outputs")
                    if isinstance(binding.get("skip_skill_runtime_outputs"), bool)
                    else True
                ),
            )
        )

    if unresolved_paths:
        raise ValueError(_missing_external_skill_sources_message(unresolved_paths))
    return selected_sources


def augment_stage_plan_with_selected_external_skill_bindings(
    stage_plan: StagePlan,
    *,
    selected_skill_paths: Optional[set[str]],
    skills_plan_json: Optional[str],
    target=None,
) -> StagePlan:
    selected_sources = selected_external_skill_bindings(
        stage_plan.tree_sources,
        selected_skill_paths=selected_skill_paths,
        skills_plan_json=skills_plan_json,
        target=target,
    )
    if not selected_sources:
        return stage_plan

    def packaged_logical_path(item: SelectedExternalSkillBinding) -> str:
        return str(
            call_optional_target_hook(
                target,
                "canonicalize_selection_path",
                item.logical_path,
                default=item.logical_path,
            )
        )

    extra_tree_sources: list[StageTreeSource] = []
    for item in selected_sources:
        logical_path = packaged_logical_path(item)
        extra_tree_sources.append(StageTreeSource(
            source_root=item.source_path,
            relative_target_root=Path(logical_path),
            display_prefix=logical_path,
            source_key=logical_path,
            source_value="external_skill_source",
            skip_skill_runtime_outputs=item.skip_skill_runtime_outputs,
        ))
    return StagePlan(
        tree_sources=[*stage_plan.tree_sources, *extra_tree_sources],
        file_sources=stage_plan.file_sources,
        metadata=dict(stage_plan.metadata),
    )


__all__ = [
    "SelectedExternalSkillBinding",
    "augment_stage_plan_with_selected_external_skill_bindings",
    "compute_skill_snapshot_digest",
    "load_external_skill_sources_payload",
    "selected_external_skill_bindings",
]
