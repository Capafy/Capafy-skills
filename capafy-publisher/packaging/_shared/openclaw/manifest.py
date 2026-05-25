from __future__ import annotations
from typing import Optional



_MISSING = object()

_SELECTION_RUNTIME_VALIDATION_LABEL = "agent.selected_units.runtime_validation"


def confirmed_openclaw_skills_from_manifest(payload: Optional[dict]) -> Optional[list[dict]]:
    if payload is None:
        return None

    runtime_validation = payload.get("runtime_validation", _MISSING)
    if runtime_validation is _MISSING:
        raise ValueError(f"{_SELECTION_RUNTIME_VALIDATION_LABEL} is missing runtime_validation")
    if not isinstance(runtime_validation, dict):
        raise ValueError(f"{_SELECTION_RUNTIME_VALIDATION_LABEL} runtime_validation must be an object")

    raw_items = runtime_validation.get("openclaw_confirmed_skills", _MISSING)
    if raw_items is _MISSING:
        raise ValueError(f"{_SELECTION_RUNTIME_VALIDATION_LABEL} is missing openclaw_confirmed_skills")
    if not isinstance(raw_items, list):
        raise ValueError(f"{_SELECTION_RUNTIME_VALIDATION_LABEL} openclaw_confirmed_skills must be an array")

    confirmed_skills: list[dict] = []
    seen_paths: set[str] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            raise ValueError(f"{_SELECTION_RUNTIME_VALIDATION_LABEL} openclaw_confirmed_skills items must be objects")
        name = str(item.get("name", "")).strip()
        skill_key = str(item.get("skill_key", "") or name).strip()
        path = str(item.get("path", "")).strip()
        if not name or not path:
            raise ValueError(f"{_SELECTION_RUNTIME_VALIDATION_LABEL} openclaw_confirmed_skills items are missing name/path")
        if path in seen_paths:
            continue
        confirmed_skills.append(
            {
                "name": name,
                "skill_key": skill_key,
                "path": path,
            }
        )
        seen_paths.add(path)
    return confirmed_skills


__all__ = [
    "confirmed_openclaw_skills_from_manifest",
]
