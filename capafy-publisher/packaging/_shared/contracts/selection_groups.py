from __future__ import annotations

from pathlib import PurePosixPath
from typing import List, Optional, TypedDict

from .selectable import is_absolute_like_path, normalize_text
from .path_shapes import is_cron_unit_type, is_plugin_unit_type


SELECTION_GROUP_KEYS = (
    "skills",
    "plugins",
    "crons",
    "workspace_documents",
)
RUNTIME_SELECTION_GROUP_KEYS = (
    "skills",
    "plugins",
    "crons",
)
_DEFAULT_SELECTION = "selected"







class CronSchedule(TypedDict, total=False):
    kind: str
    expr: str
    tz: str


class CronPayload(TypedDict, total=False):
    prompt: str


class CronGroupItem(TypedDict, total=False):
    id: str
    name: str
    selection: str
    schedule: CronSchedule
    payload: CronPayload
    decision: str


class GroupItem(TypedDict, total=False):
    path: str
    selection: str
    purpose: str
    requires_user_confirmation: bool
    name: str
    description: str
    decision: str
    origin: str
    source_path: str
    source_root: str
    source_kind: str
    binding_kind: str
    skip_skill_runtime_outputs: bool
    config_ref: str
    skill_key: str
    synopsis: str
    reasons: List[str]


class SelectionGroups(TypedDict, total=False):
    skills: List[GroupItem]
    plugins: List[GroupItem]
    crons: List[CronGroupItem]
    workspace_documents: List[GroupItem]







def is_selected_selection_group_item(item: object) -> bool:
    if not isinstance(item, dict):
        return False
    selection = normalize_text(item.get("selection")).lower()
    return selection == _DEFAULT_SELECTION


def _purpose_from_reasons(reasons: object) -> str:
    if not isinstance(reasons, list):
        return ""
    for item in reasons:
        normalized = normalize_text(item)
        if normalized:
            return normalized
    return ""


def _explicit_purpose(item: dict) -> str:
    explicit = normalize_text(item.get("purpose"))
    if explicit:
        return explicit
    return _purpose_from_reasons(item.get("reasons"))


def _document_purpose(path: str) -> str:
    filename = PurePosixPath(path).name.lower()
    if filename == "agents.md":
        return "Workflow instructions and behavioral constraints"
    if filename == "soul.md":
        return "Persona definition and long-term behavioral constraints"
    if filename == "tools.md":
        return "Tool instructions and invocation context"
    if filename == "user.md":
        return "User background and preference context"
    if filename == "heartbeat.md":
        return "Runtime state and recurring task notes"
    if filename == "memory.md" or "/memory/" in f"/{path.lower()}":
        return "Memory context and accumulated reference material"
    return "Workspace document context"


def _unit_purpose(item: dict) -> str:
    explicit = _explicit_purpose(item)
    if explicit:
        return explicit
    unit_type = normalize_text(item.get("unit_type"))
    if is_plugin_unit_type(unit_type):
        return "Workflow plugin extension"
    if is_cron_unit_type(unit_type):
        return "Workflow scheduled task"
    return "Workflow execution unit"







def _base_group_item(
    item: dict,
    *,
    purpose: str,
    requires_user_confirmation: bool,
) -> GroupItem:
    payload: GroupItem = {
        "path": normalize_text(item.get("path")),
        "selection": _DEFAULT_SELECTION,
        "purpose": normalize_text(purpose) or "Purpose pending confirmation",
        "requires_user_confirmation": bool(requires_user_confirmation),
    }
    for key in (
        "name",
        "description",
        "decision",
        "origin",
        "source_path",
        "source_root",
        "source_kind",
        "binding_kind",
        "config_ref",
        "skill_key",
        "synopsis",
    ):
        value = item.get(key)
        normalized = normalize_text(value)
        if normalized:
            payload[key] = normalized  # type: ignore[literal-required]
    skip_skill_runtime_outputs = item.get("skip_skill_runtime_outputs")
    if isinstance(skip_skill_runtime_outputs, bool):
        payload["skip_skill_runtime_outputs"] = skip_skill_runtime_outputs
    reasons = item.get("reasons")
    if isinstance(reasons, list):
        normalized_reasons = [normalize_text(reason) for reason in reasons if normalize_text(reason)]
        if normalized_reasons:
            payload["reasons"] = normalized_reasons
    return payload


def _cron_schedule_payload(schedule: object) -> CronSchedule:
    if not isinstance(schedule, dict):
        return {}
    normalized: CronSchedule = {}
    for key in ("kind", "expr", "tz"):
        value = normalize_text(schedule.get(key))
        if value:
            normalized[key] = value  # type: ignore[literal-required]
    return normalized


def _cron_prompt_payload(payload: object) -> CronPayload:
    if not isinstance(payload, dict):
        return {}
    prompt = normalize_text(payload.get("prompt"))
    if not prompt:
        return {}
    return {"prompt": prompt}


def _cron_group_item(
    item: dict,
    *,
    preserve_selection: bool = False,
) -> Optional[CronGroupItem]:
    cron_id = normalize_text(item.get("id"))
    name = normalize_text(item.get("name"))
    schedule = _cron_schedule_payload(item.get("schedule"))
    payload = _cron_prompt_payload(item.get("payload"))
    if not cron_id or not name or not schedule or not payload:
        return None
    result: CronGroupItem = {
        "id": cron_id,
        "name": name,
        "selection": _DEFAULT_SELECTION,
        "schedule": schedule,
        "payload": payload,
    }
    selection = normalize_text(item.get("selection"))
    if preserve_selection and selection and selection.lower() != _DEFAULT_SELECTION:
        result["selection"] = selection
    decision = normalize_text(item.get("decision"))
    if decision:
        result["decision"] = decision
    return result







def _group_selected_units(
    selected_units: list,
    *,
    requires_user_confirmation: bool,
) -> dict:
    grouped: dict = {
        "skills": [],
        "plugins": [],
        "crons": [],
    }
    for item in selected_units:
        selection = normalize_text(item.get("selection")).lower()
        if selection and selection != _DEFAULT_SELECTION:
            continue
        path = normalize_text(item.get("path"))
        if not path:
            continue
        if is_absolute_like_path(path):
            raise ValueError("selected_units item path must be a logical path, not an absolute path")
        unit_type = normalize_text(item.get("unit_type"))
        target_key = "skills"
        if is_plugin_unit_type(unit_type):
            target_key = "plugins"
        elif is_cron_unit_type(unit_type):
            target_key = "crons"
        if target_key == "crons":
            cron_item = _cron_group_item(item)
            if cron_item:
                grouped[target_key].append(cron_item)
            continue
        grouped[target_key].append(
            _base_group_item(
                item,
                purpose=_unit_purpose(item),
                requires_user_confirmation=requires_user_confirmation,
            )
        )
    return grouped


def build_selected_selection_groups(
    *,
    selected_units: Optional[list] = None,
    context_sources_input: Optional[dict] = None,
) -> SelectionGroups:
    if selected_units is None:
        normalized_selected_units: list = []
    else:
        if not isinstance(selected_units, list):
            raise ValueError("selected_units must be an array")
        for item in selected_units:
            if not isinstance(item, dict):
                raise ValueError("selected_units items must be objects")
        normalized_selected_units = selected_units
    groups: SelectionGroups = {key: [] for key in SELECTION_GROUP_KEYS}  # type: ignore[misc]
    groups.update(  # type: ignore[typeddict-item]
        _group_selected_units(
            normalized_selected_units,
            requires_user_confirmation=True,
        )
    )

    if context_sources_input is None:
        candidates: dict = {}
    else:
        if not isinstance(context_sources_input, dict):
            raise ValueError("context_sources_input must be an object")
        candidates = context_sources_input
    if "workspace_documents" in candidates and not isinstance(candidates.get("workspace_documents"), list):
        raise ValueError("workspace_documents must be an array")
    for item in candidates.get("workspace_documents", []):
        if not isinstance(item, dict):
            raise ValueError("workspace_documents items must be objects")
    for item in candidates.get("workspace_documents", []):
        path = normalize_text(item.get("path"))
        if not path:
            continue
        selection = normalize_text(item.get("selection")).lower()
        if selection and selection != _DEFAULT_SELECTION:
            continue
        groups["workspace_documents"].append(
            _base_group_item(
                item,
                purpose=_explicit_purpose(item) or _document_purpose(path),
                requires_user_confirmation=True,
            )
        )
    return groups


def normalize_documented_selection_groups(raw: object) -> SelectionGroups:
    groups: SelectionGroups = {key: [] for key in SELECTION_GROUP_KEYS}  # type: ignore[misc]
    if not isinstance(raw, dict):
        return groups
    for key in SELECTION_GROUP_KEYS:
        value = raw.get(key, [])
        if not isinstance(value, list):
            continue
        items: list = []
        for item in value:
            if not isinstance(item, dict):
                continue
            if key == "crons":
                normalized_cron = _cron_group_item(item, preserve_selection=True)
                if normalized_cron is not None:
                    items.append(normalized_cron)
                continue
            path = normalize_text(item.get("path"))
            if not path:
                continue
            normalized = dict(item)
            normalized.pop("confidence", None)
            normalized.pop("unit_type", None)
            normalized["path"] = path
            normalized["purpose"] = normalize_text(item.get("purpose")) or "Purpose pending confirmation"
            normalized["requires_user_confirmation"] = bool(item.get("requires_user_confirmation"))
            selection = normalize_text(item.get("selection")) or _DEFAULT_SELECTION
            normalized["selection"] = selection
            items.append(normalized)
        groups[key] = items  # type: ignore[literal-required]
    return groups


def strip_default_selection_fields(groups: SelectionGroups) -> SelectionGroups:
    stripped_groups: SelectionGroups = {key: [] for key in SELECTION_GROUP_KEYS}  # type: ignore[misc]
    for key in SELECTION_GROUP_KEYS:
        for item in groups.get(key, []):  # type: ignore[literal-required]
            normalized = dict(item)
            if normalize_text(normalized.get("selection")).lower() == _DEFAULT_SELECTION:
                normalized.pop("selection", None)
            stripped_groups[key].append(normalized)  # type: ignore[literal-required]
    return stripped_groups


def selected_items_for_group(groups: SelectionGroups, key: str) -> list:
    return [
        item
        for item in groups.get(key, [])  # type: ignore[literal-required]
        if is_selected_selection_group_item(item)
    ]


def validate_buyout_skill_count(raw: object) -> SelectionGroups:
    groups = normalize_documented_selection_groups(raw)
    selected_skills = selected_items_for_group(groups, "skills")
    if len(selected_skills) != 1:
        raise ValueError("buyout only supports exactly one selected skill")
    return groups


__all__ = [
    "RUNTIME_SELECTION_GROUP_KEYS",
    "SELECTION_GROUP_KEYS",
    "CronGroupItem",
    "CronPayload",
    "CronSchedule",
    "GroupItem",
    "SelectionGroups",
    "build_selected_selection_groups",
    "is_selected_selection_group_item",
    "normalize_documented_selection_groups",
    "selected_items_for_group",
    "strip_default_selection_fields",
    "validate_buyout_skill_count",
]
