from __future__ import annotations
from typing import Optional

from pathlib import Path, PurePosixPath

from packaging._shared.contracts.path_shapes import rootless_skill_path
from packaging._shared.contracts.selection_groups import build_selected_selection_groups
from packaging._shared.contracts.selectable import normalize_text
from packaging._shared.common.constants import SKILL_CONFIG_PATH
from packaging._shared.runtimes.contracts import call_optional_target_hook

from .selection_candidates import DiscoveryUnit, candidate_context_input, candidate_selection_groups
from .workspace_documents import discover_documents
from .runtime_units import discover_units


CANDIDATE_REASON_LIMIT = 3
CANDIDATE_GROUP_KEYS = ("skills", "plugins", "crons")
DEFAULT_UNIT_PURPOSES = {
    "Workflow execution unit",
    "Workflow plugin extension",
    "Workflow scheduled task",
}
BRIEF_ITEM_KEYS = (
    "path",
    "name",
    "description",
    "unit_type",
    "suggested",
    "reasons",
)


def _candidate_reasons(entry: DiscoveryUnit) -> list[str]:
    reasons: list[str] = []
    for key in ("reasons", "suspicious_reasons"):
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


def _path_is_nested_under(parent: str, child: str) -> bool:
    normalized_parent = _normalize_discovery_path(parent)
    normalized_child = _normalize_discovery_path(child)
    return bool(
        normalized_parent
        and normalized_child
        and normalized_child != normalized_parent
        and normalized_child.startswith(f"{normalized_parent}/")
    )


def _is_self_publisher_candidate(entry: DiscoveryUnit) -> bool:
    name = normalize_text(entry.get("name")).lower()
    path = _normalize_discovery_path(entry.get("path")).lower()
    source_path = str(entry.get("source_path") or entry.get("source_root") or "").strip()
    if source_path:
        try:
            if Path(source_path).expanduser().resolve(strict=False) == SKILL_CONFIG_PATH.parent:
                return True
        except OSError:
            pass
    if name == "capafy-publisher" or PurePosixPath(path).name.lower() == "capafy-publisher":
        return True
    return False


def _is_plugin_skill_path(path: str) -> bool:
    return "/plugins/" in f"/{_normalize_discovery_path(path)}/"


def _suppress_nested_skill_copies(candidates: list[DiscoveryUnit]) -> list[DiscoveryUnit]:
    parent_paths = {
        _normalize_discovery_path(item.get("path"))
        for item in candidates
        if str(item.get("unit_type", "")) == "skill" and _normalize_discovery_path(item.get("path"))
    }
    if not parent_paths:
        return candidates
    filtered: list[DiscoveryUnit] = []
    for item in candidates:
        if str(item.get("unit_type", "")) != "skill":
            filtered.append(item)
            continue
        path = _normalize_discovery_path(item.get("path"))
        if _is_plugin_skill_path(path):
            filtered.append(item)
            continue
        if any(_path_is_nested_under(parent, path) for parent in parent_paths):
            continue
        filtered.append(item)
    return filtered


def _candidate_search_text(item: dict) -> str:
    return " ".join(
        normalize_text(item.get(key)).lower()
        for key in ("name", "description", "synopsis", "path")
        if normalize_text(item.get(key))
    )


def _query_tokens(*values: Optional[str]) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        text = normalize_text(value).lower()
        token = ""
        for char in text:
            if char.isalnum():
                token += char
            elif token:
                if len(token) >= 3:
                    tokens.add(token)
                token = ""
        if token and len(token) >= 3:
            tokens.add(token)
    return tokens


def _candidate_match_score(item: dict, query_tokens: set[str]) -> int:
    if not query_tokens:
        return 0
    search_text = _candidate_search_text(item)
    score = 0
    for token in query_tokens:
        if token in search_text:
            score += 1
    return score


def _rank_and_mark_suggestion(groups: dict, *, title: Optional[str], description: Optional[str]) -> dict:
    query_tokens = _query_tokens(title, description)
    if not query_tokens:
        return groups

    ranked_groups = dict(groups)
    best_score = 0
    best_key = ""
    for key in CANDIDATE_GROUP_KEYS:
        items = ranked_groups.get(key)
        if not isinstance(items, list):
            continue
        scored: list[tuple[int, int, dict]] = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            score = _candidate_match_score(item, query_tokens)
            if score > best_score:
                best_score = score
                best_key = key
            scored.append((score, index, item))
        scored.sort(key=lambda entry: (-entry[0], entry[1]))
        ranked_groups[key] = [item for _score, _index, item in scored]

    if best_score <= 0 or not best_key:
        return ranked_groups
    best_item = ranked_groups[best_key][0] if ranked_groups.get(best_key) else None
    if isinstance(best_item, dict):
        best_item["suggested"] = True
    return ranked_groups


def _brief_item(item: dict) -> dict:
    return {
        key: item[key]
        for key in BRIEF_ITEM_KEYS
        if key in item and item[key] not in ("", [], None)
    }


def _brief_groups(groups: dict) -> dict:
    payload = dict(groups)
    for key in CANDIDATE_GROUP_KEYS:
        items = payload.get(key)
        if isinstance(items, list):
            payload[key] = [_brief_item(item) if isinstance(item, dict) else item for item in items]
    return payload


def _format_candidate_groups(
    groups: dict,
    *,
    brief: bool = False,
    title: Optional[str] = None,
    description: Optional[str] = None,
) -> dict:
    formatted = dict(groups)
    for key in CANDIDATE_GROUP_KEYS:
        items = formatted.get(key)
        if not isinstance(items, list):
            continue
        formatted_items = []
        for item in items:
            if not isinstance(item, dict):
                formatted_items.append(item)
                continue
            payload = dict(item)
            payload.pop("suggested", None)
            if normalize_text(payload.get("purpose")) in DEFAULT_UNIT_PURPOSES:
                payload.pop("purpose", None)
            formatted_items.append(payload)
        formatted[key] = formatted_items
    formatted = _rank_and_mark_suggestion(formatted, title=title, description=description)
    if brief:
        formatted = _brief_groups(formatted)
    return formatted


def _candidate_groups_for_output(
    candidates: list[DiscoveryUnit],
    *,
    target=None,
    brief: bool = False,
    title: Optional[str] = None,
    description: Optional[str] = None,
) -> dict:
    return _format_candidate_groups(
        candidate_selection_groups(candidates, target=target),
        brief=brief,
        title=title,
        description=description,
    )


def format_discovery_payload(
    discovery_payload: dict,
    *,
    brief: bool = False,
    title: Optional[str] = None,
    description: Optional[str] = None,
) -> dict:
    return _format_candidate_groups(
        discovery_payload,
        brief=brief,
        title=title,
        description=description,
    )


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


def _skill_dedupe_key(entry: DiscoveryUnit) -> Optional[str]:
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
        if _is_self_publisher_candidate(entry):
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
    return _suppress_nested_skill_copies([payload for _index, payload in ordered_candidates])


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
    target_name: Optional[str] = None,
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


def resolve_skills_for_target(
    *,
    target_name: Optional[str] = None,
    runtime_dir: str,
    brief: bool = False,
    title: Optional[str] = None,
    description: Optional[str] = None,
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
    return _candidate_groups_for_output(
        _candidate_units(discovered_units, target=target),
        target=target,
        brief=brief,
        title=title,
        description=description,
    )


__all__ = [
    "discover_context_selection_groups_for_target",
    "format_discovery_payload",
    "resolve_skills_for_target",
]
