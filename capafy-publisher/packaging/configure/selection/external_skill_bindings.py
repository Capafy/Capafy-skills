from __future__ import annotations
from typing import Optional

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from packaging._shared.runtimes.contracts import call_optional_target_hook
from packaging._shared.contracts.stage_plan import StagePlan, StageTreeSource

from packaging._shared.contracts.selectable import (
    candidate_path_for_logical_path as _candidate_path_for_logical_path,
)
from packaging.configure.selection.unit_types import infer_selection_unit_type
from packaging.configure.selection.external_skill_payload import load_external_skill_sources_payload
from packaging.configure.selection.external_skill_snapshot import compute_skill_snapshot_digest


@dataclass(frozen=True)
class SelectedExternalSkillBinding:
    logical_path: str
    source_path: Path
    origin: str
    origin_ref: str
    snapshot_digest: str = ""
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
        f"{sample}{suffix}; rerun the upstream selection confirmation step and regenerate skills_plan with "
        "selection_groups.skills[].source_path. Local scan/stage no longer rebuild these sources automatically."
    )


def _invalid_external_skill_source_message(logical_path: str, detail: str) -> str:
    return (
        f"selection_groups.skills source_path for selected skill {logical_path} {detail}; rerun the upstream selection confirmation "
        "step and regenerate skills_plan"
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
                origin=str(binding.get("origin", "")),
                origin_ref=str(binding.get("origin_ref", "")),
                snapshot_digest=expected_snapshot_digest,
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

    extra_tree_sources = [
        StageTreeSource(
            source_root=item.source_path,
            relative_target_root=Path(packaged_logical_path(item)),
            display_prefix=packaged_logical_path(item),
            source_key=packaged_logical_path(item),
            source_value="external_skill_source",
            skip_skill_runtime_outputs=item.skip_skill_runtime_outputs,
        )
        for item in selected_sources
    ]
    return StagePlan(
        tree_sources=[*stage_plan.tree_sources, *extra_tree_sources],
        file_sources=stage_plan.file_sources,
        metadata=dict(stage_plan.metadata),
    )


__all__ = [
    "SelectedExternalSkillBinding",
    "augment_stage_plan_with_selected_external_skill_bindings",
    "compute_skill_snapshot_digest",
    "selected_external_skill_bindings",
]
