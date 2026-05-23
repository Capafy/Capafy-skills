from __future__ import annotations

from pathlib import PurePosixPath

from packaging._shared.contracts.path_shapes import rootless_skill_path
from packaging._shared.contracts.selection_groups import build_selected_selection_groups
from packaging._shared.runtimes.contracts import call_optional_target_hook

from .selection_candidates import DiscoveryUnit, candidate_context_input, candidate_selection_groups
from .workspace_documents import discover_documents
from .runtime_units import discover_units


CANDIDATE_REASON_LIMIT = 3


def _candidate_reasons(entry: DiscoveryUnit) -> list[str]:
    reasons: list[str] = []
    for key in ("reasons", "structural_reasons", "suspicious_reasons"):
        raw = entry.get(key, [])
        if not isinstance(raw, list):
            continue
        for item in raw:
            reason = str(item).strip()
            if reason and reason not in reasons:
                reasons.append(reason)
                if len(reasons) >= CANDIDATE_REASON_LIMIT:
                    return reasons
    return reasons


def _candidate_payload(entry: DiscoveryUnit) -> DiscoveryUnit:
    payload = dict(entry)
    reasons = _candidate_reasons(entry)
    if reasons:
        payload["reasons"] = reasons
    return payload


def _normalize_discovery_path(value: object) -> str:
    normalized = PurePosixPath(str(value or "").strip().rstrip("/")).as_posix()
    return "" if normalized == "." else normalized


def _skill_root_prefix(path: object) -> str:
    normalized = _normalize_discovery_path(path)
    if not normalized:
        return ""
    parts = [part for part in PurePosixPath(normalized).parts if part and part != "."]
    for index, part in enumerate(parts):
        if part == "skills":
            return PurePosixPath(*parts[: index + 1]).as_posix()
    return ""


def _entry_discovery_root(entry: DiscoveryUnit) -> str:
    for key in ("discovery_root", "source_root"):
        normalized = _normalize_discovery_path(entry.get(key, ""))
        if normalized:
            return normalized
    return _skill_root_prefix(entry.get("path", ""))


def _skill_dedupe_key(entry: DiscoveryUnit) -> str | None:
    if str(entry.get("unit_type", "")) != "skill":
        return None
    path = _normalize_discovery_path(entry.get("path", ""))
    if not path:
        return None
    if "/plugins/" in f"/{path}/" and "/skills/" in path:
        return path
    return rootless_skill_path(path) or path


def _entry_precedence_index(entry: DiscoveryUnit, *, target=None) -> int:
    precedence = tuple(
        call_optional_target_hook(
            target,
            "discovery_skill_precedence",
            default=(),
        )
    )
    if not precedence:
        return 0

    discovery_root = _entry_discovery_root(entry)
    for index, prefix in enumerate(precedence):
        normalized_prefix = _normalize_discovery_path(prefix)
        if normalized_prefix and (
            discovery_root == normalized_prefix or discovery_root.startswith(f"{normalized_prefix}/")
        ):
            return index
    return len(precedence)


def _entry_preference_key(
    entry: DiscoveryUnit,
    *,
    target=None,
    original_index: int = 0,
) -> tuple[int, int, str, str, int]:
    source_kind = str(entry.get("source_kind", "")).strip()
    return (
        _entry_precedence_index(entry, target=target),
        1 if source_kind == "external_skill_dir" else 0,
        _entry_discovery_root(entry),
        _normalize_discovery_path(entry.get("path", "")),
        original_index,
    )


def _candidate_units(discovered_units: list[DiscoveryUnit], *, target=None) -> list[DiscoveryUnit]:
    ordered_candidates: list[tuple[int, DiscoveryUnit]] = []
    skill_winners: dict[str, tuple[tuple[int, int, str, str, int], int, DiscoveryUnit]] = {}

    for index, entry in enumerate(discovered_units):
        if str(entry.get("unit_type", "")) == "skill" and not bool(entry.get("has_primary_doc")):
            continue
        payload = _candidate_payload(entry)
        dedup_key = _skill_dedupe_key(payload)
        if not dedup_key:
            ordered_candidates.append((index, payload))
            continue

        preference = _entry_preference_key(payload, target=target, original_index=index)
        current = skill_winners.get(dedup_key)
        if current is None or preference < current[0]:
            skill_winners[dedup_key] = (preference, index, payload)

    ordered_candidates.extend((index, payload) for _preference, index, payload in skill_winners.values())
    ordered_candidates.sort(key=lambda item: item[0])
    return [payload for _index, payload in ordered_candidates]


def _target_stage_plan(target, runtime_dir: str):
    normalized_runtime_dir = str(runtime_dir or "").strip()
    if not normalized_runtime_dir:
        raise ValueError("runtime_dir is required")
    normalized_runtime_dir = call_optional_target_hook(
        target,
        "prepare_runtime_dir",
        normalized_runtime_dir,
        default=normalized_runtime_dir,
    )
    stage_plan = target.build_stage_plan(normalized_runtime_dir)
    return normalized_runtime_dir, stage_plan


def discover_context_selection_groups_for_target(
    *,
    target_name: str | None = None,
    runtime_dir: str,
) -> dict[str, list[dict]]:
    from packaging.runtimes import get_default_target, get_target

    try:
        target = get_target(target_name) if target_name else get_default_target()
        resolved_runtime_dir, stage_plan = _target_stage_plan(target, runtime_dir)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    documents = discover_documents(stage_plan, runtime_dir=resolved_runtime_dir, target=target)
    context_sources_input = candidate_context_input(
        documents,
        target=target,
    )
    return build_selected_selection_groups(
        selected_units=[],
        context_sources_input=context_sources_input,
    )


def resolve_skills(
    discovered_units: list[DiscoveryUnit],
    *,
    target=None,
) -> dict:
    return candidate_selection_groups(
        _candidate_units(discovered_units, target=target),
        target=target,
    )


def resolve_skills_for_target(
    *,
    target_name: str | None = None,
    runtime_dir: str,
) -> dict:
    from packaging.runtimes import get_default_target, get_target

    try:
        target = get_target(target_name) if target_name else get_default_target()
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    try:
        _resolved_runtime_dir, stage_plan = _target_stage_plan(target, runtime_dir)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    discovered_units, _suspicious_units = discover_units(stage_plan, target=target)
    return resolve_skills(
        discovered_units,
        target=target,
    )


__all__ = [
    "discover_context_selection_groups_for_target",
    "resolve_skills",
    "resolve_skills_for_target",
]
