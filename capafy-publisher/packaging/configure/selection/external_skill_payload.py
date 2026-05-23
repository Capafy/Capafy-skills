from __future__ import annotations

import json
from pathlib import PurePosixPath

from packaging._shared.contracts.selectable import validate_logical_path


def load_external_skill_sources_payload(
    *,
    skills_plan_json: str | None,
) -> list[dict]:
    if not skills_plan_json:
        return []
    try:
        payload = json.loads(skills_plan_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"selected skills JSON parse failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("selected skills JSON top-level value must be an object")

    raw_sources: list[tuple[object, str, str, str, str]] = []
    raw_groups = payload.get("selection_groups")
    if isinstance(raw_groups, dict):
        raw_skills = raw_groups.get("skills", [])
        if isinstance(raw_skills, list):
            for item in raw_skills:
                if (
                    isinstance(item, dict)
                    and str(item.get("source_path", "")).strip()
                    and str(item.get("binding_kind", "")).strip() == "external_skill_dir"
                ):
                    raw_sources.append(
                        (
                            {
                                "logical_path": item.get("logical_path") or item.get("path"),
                                "source_path": item.get("source_path"),
                                "binding_kind": item.get("binding_kind"),
                                "unit_type": item.get("unit_type", "skill"),
                                "origin": item.get("origin"),
                                "origin_ref": item.get("origin_ref"),
                                "snapshot_digest": item.get("snapshot_digest"),
                                "source_kind": item.get("source_kind"),
                                "skip_skill_runtime_outputs": item.get("skip_skill_runtime_outputs"),
                            },
                            "selection_groups.skills item",
                            "selection_groups.skills item path",
                            "selection_groups.skills items with source_path must include path and source_path",
                            "selection_groups.skills items must be objects",
                        )
                    )

    if not raw_sources:
        return []

    normalized: list[dict] = []
    seen: set[str] = set()
    for raw_item, item_label, logical_path_label, required_fields_message, objects_message in raw_sources:
        if not isinstance(raw_item, dict):
            raise ValueError(objects_message)
        logical_path = PurePosixPath(
            validate_logical_path(
                raw_item.get("logical_path", ""),
                label=logical_path_label,
            ).rstrip("/")
        ).as_posix()
        source_path = str(raw_item.get("source_path", "")).strip()
        unit_type = str(raw_item.get("unit_type", "skill")).strip() or "skill"
        binding_kind = str(raw_item.get("binding_kind", "")).strip()
        if not logical_path or not source_path:
            raise ValueError(required_fields_message)
        if unit_type != "skill":
            raise ValueError(f"{item_label} unit_type must be skill")
        if binding_kind != "external_skill_dir":
            continue
        if logical_path in seen:
            continue
        seen.add(logical_path)
        normalized.append(
            {
                "logical_path": logical_path,
                "source_path": source_path,
                "binding_kind": binding_kind,
                "unit_type": unit_type,
                "origin": str(raw_item.get("origin") or "").strip(),
                "origin_ref": str(raw_item.get("origin_ref") or "").strip(),
                "snapshot_digest": str(raw_item.get("snapshot_digest") or "").strip(),
                "source_kind": str(raw_item.get("source_kind") or "").strip(),
                "skip_skill_runtime_outputs": raw_item.get("skip_skill_runtime_outputs"),
            }
        )
    return normalized


__all__ = ["load_external_skill_sources_payload"]
