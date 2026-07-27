from __future__ import annotations

from packaging.runtimes.openclaw.skill_metadata import (
    runtime_skill_key_from_entry,
    runtime_skill_name_from_entry,
)


def build_openclaw_selection_runtime_validation(
    *,
    selected_paths: set[str],
    included_skills: list[dict],
) -> dict:
    entries: list[dict] = []
    seen_paths: set[str] = set()
    seen_skill_keys: dict[str, str] = {}

    def append_entry(name: str, skill_key: str, path: str) -> None:
        if not name or not path or path in seen_paths:
            return
        normalized_skill_key = skill_key or name
        existing_path = seen_skill_keys.get(normalized_skill_key)
        if existing_path and existing_path != path:
            raise ValueError(
                "openclaw confirmed skills contain duplicate skill_key "
                f"{normalized_skill_key!r}: {existing_path!r} and {path!r}"
            )
        entries.append(
            {
                "name": name,
                "skill_key": normalized_skill_key,
                "path": path,
            }
        )
        seen_paths.add(path)
        seen_skill_keys[normalized_skill_key] = path

    for item in included_skills:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).strip()
        name = runtime_skill_name_from_entry(item)
        skill_key = runtime_skill_key_from_entry(item)
        if not path or not name:
            continue
        if path in selected_paths:
            append_entry(name, skill_key, path)

    entries.sort(key=lambda item: item["path"])
    return {"openclaw_confirmed_skills": entries}


__all__ = ["build_openclaw_selection_runtime_validation"]
