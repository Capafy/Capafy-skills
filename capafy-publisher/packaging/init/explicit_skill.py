from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from packaging._shared.contracts.selection_groups import (
    SELECTION_GROUP_KEYS,
    RUNTIME_SELECTION_GROUP_KEYS,
    is_selected_selection_group_item,
    normalize_documented_selection_groups,
)
from packaging._shared.contracts.selectable import is_absolute_like_path
from packaging.configure.selection.support import build_unit_metadata, finalize_selectable_entry
from packaging.runtimes import get_target


EXPLICIT_SKILL_SOURCE_KIND = "explicit_skill_dir"
EXPLICIT_SKILL_BINDING_KIND = "external_skill_dir"




_DEFAULT_SKILL_PREFIX_BY_ENV = {
    "claude": ".claude/skills",
    "claude_code": ".claude/skills",
    "codex": ".agents/skills",
    "openclaw": ".openclaw/skills",
}


def _env_family(env_id: str) -> str:
    normalized = str(env_id or "").strip()
    if normalized in {"claude", "claude_code"}:
        return "claude_code"
    for prefix in ("openclaw", "codex"):
        if normalized == prefix or normalized.startswith(f"{prefix}_"):
            return prefix
    return normalized


def _logical_path_for_skill_dir(skill_root: Path, env_id: str) -> str:
    family = _env_family(env_id)
    prefix = _DEFAULT_SKILL_PREFIX_BY_ENV.get(family, "skills")
    return (PurePosixPath(prefix) / skill_root.name).as_posix()


def resolve_explicit_skill(skill_dir: str, *, env_id: str) -> dict[str, Any]:
    normalized = str(skill_dir or "").strip()
    if not normalized:
        raise ValueError("skill_dir is required when explicit skill selection is enabled")
    try:
        source_root = Path(normalized).expanduser().resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError(f"skill_dir does not exist: {skill_dir}") from exc
    if not source_root.is_dir():
        raise ValueError(f"skill_dir must be a directory: {source_root}")
    if not (source_root / "SKILL.md").is_file():
        raise ValueError(f"skill_dir must contain SKILL.md: {source_root}")

    logical_path = _logical_path_for_skill_dir(source_root, env_id)
    meta = build_unit_metadata(source_root, "skill")
    entry: dict[str, Any] = {
        "path": logical_path,
        "name": meta["name"],
        "description": meta["description"],
        "source_root": str(source_root),
        "discovery_root": EXPLICIT_SKILL_SOURCE_KIND,
        "unit_type": "skill",
        "has_primary_doc": meta["has_primary_doc"],
        "has_skill_md": meta["has_primary_doc"],
        "file_count": meta["file_count"],
        "size_bytes": meta["size_bytes"],
        "synopsis": meta["synopsis"],
        "suspicious_reasons": meta["suspicious_reasons"],
        "source_path": str(source_root),
        "binding_kind": EXPLICIT_SKILL_BINDING_KIND,
        "source_kind": EXPLICIT_SKILL_SOURCE_KIND,
        "skip_skill_runtime_outputs": True,
    }
    try:
        entry = finalize_selectable_entry(get_target(env_id), entry, unit_path=source_root)
    except ValueError:


        pass
    entry.setdefault("reasons", ["Explicit skill_dir provided by creator"])
    return entry


def _selected_explicit_skill_item(explicit_skill: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(explicit_skill.get("path", "")).strip(),
        "name": str(explicit_skill.get("name", "")).strip(),
        "description": str(explicit_skill.get("description", "")).strip(),
        "source_path": str(explicit_skill.get("source_path", "")).strip(),
        "binding_kind": EXPLICIT_SKILL_BINDING_KIND,
        "source_kind": EXPLICIT_SKILL_SOURCE_KIND,
        "unit_type": "skill",
        "selection": "selected",
        "requires_user_confirmation": True,
        "skip_skill_runtime_outputs": bool(explicit_skill.get("skip_skill_runtime_outputs", True)),
    }


def merge_explicit_skill_into_top_level_selections(
    selections: dict[str, Any],
    explicit_skill: dict[str, Any] | None,
) -> dict[str, Any]:
    if not explicit_skill:
        return selections

    payload = dict(selections)
    raw_skills = payload.get("skills", [])
    if not isinstance(raw_skills, list):
        return payload
    if len(raw_skills) > 1:
        raise ValueError("--skill-dir can only be used with a single selected skill")

    explicit_path = str(explicit_skill.get("path", "")).strip()
    selected_item = _selected_explicit_skill_item(explicit_skill)
    if not raw_skills:
        payload["skills"] = [selected_item]
        return payload

    item = dict(raw_skills[0])
    item_path = str(item.get("path", "")).strip()
    if item_path and item_path != explicit_path:
        raise ValueError(
            f"--skill-dir resolved to {explicit_path}, but selections.skills[0].path is {item_path}"
        )
    payload["skills"] = [
        {
            **selected_item,
            **item,
            "path": explicit_path,
            "source_path": selected_item["source_path"],
            "binding_kind": EXPLICIT_SKILL_BINDING_KIND,
            "source_kind": EXPLICIT_SKILL_SOURCE_KIND,
            "unit_type": "skill",
        }
    ]
    return payload


def discovery_payload_from_explicit_skill(explicit_skill: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    payload: dict[str, list[dict[str, Any]]] = {key: [] for key in RUNTIME_SELECTION_GROUP_KEYS}
    payload["skills"] = [dict(explicit_skill)]
    return payload


def merge_explicit_skill_into_selection_groups(
    selection_groups: dict[str, Any],
    explicit_skill: dict[str, Any] | None,
) -> dict[str, list[dict[str, Any]]]:
    groups = normalize_documented_selection_groups(selection_groups)
    if not explicit_skill:
        return groups

    explicit_path = str(explicit_skill.get("path", "")).strip()
    if not explicit_path:
        return groups

    selected_item = _selected_explicit_skill_item(explicit_skill)
    merged_groups: dict[str, list[dict[str, Any]]] = {key: list(groups.get(key, [])) for key in SELECTION_GROUP_KEYS}
    skills = merged_groups.get("skills", [])
    matched = False
    for index, item in enumerate(skills):
        if not is_selected_selection_group_item(item):
            continue
        if str(item.get("path", "")).strip() != explicit_path:
            continue
        skills[index] = {
            **selected_item,
            **item,
            "source_path": selected_item["source_path"],
            "binding_kind": EXPLICIT_SKILL_BINDING_KIND,
            "source_kind": EXPLICIT_SKILL_SOURCE_KIND,
            "unit_type": "skill",
        }
        matched = True
        break
    if not matched and not skills:
        skills.append(selected_item)
    merged_groups["skills"] = skills
    return merged_groups


def _external_skill_binding_for_manifest(item: dict[str, Any]) -> dict[str, Any] | None:
    path = str(item.get("path", "")).strip()
    source_path = str(item.get("source_path", "")).strip()
    if not source_path:
        source_root = str(item.get("source_root", "")).strip()
        if source_root and (is_absolute_like_path(source_root) or Path(source_root).expanduser().is_absolute()):
            source_path = source_root
    if not path or not source_path:
        return None
    binding_kind = str(item.get("binding_kind", EXPLICIT_SKILL_BINDING_KIND)).strip() or EXPLICIT_SKILL_BINDING_KIND
    if binding_kind != EXPLICIT_SKILL_BINDING_KIND:
        return None
    source_kind = str(item.get("source_kind", EXPLICIT_SKILL_SOURCE_KIND)).strip() or EXPLICIT_SKILL_SOURCE_KIND
    unit_type = str(item.get("unit_type", "skill")).strip() or "skill"
    if unit_type != "skill":
        return None
    payload = {
        "path": path,
        "source_path": source_path,
        "binding_kind": binding_kind,
        "source_kind": source_kind,
        "unit_type": unit_type,
        "name": str(item.get("name", "")).strip(),
        "description": str(item.get("description", "")).strip(),
        "skip_skill_runtime_outputs": (
            item.get("skip_skill_runtime_outputs")
            if isinstance(item.get("skip_skill_runtime_outputs"), bool)
            else True
        ),
    }
    return {key: value for key, value in payload.items() if value not in ("", None)}


def external_skill_bindings_for_manifest(selection_groups: object) -> list[dict[str, Any]]:
    groups = normalize_documented_selection_groups(selection_groups)
    bindings: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in groups.get("skills", []):
        binding = _external_skill_binding_for_manifest(item)
        if binding is None:
            continue
        path = binding["path"]
        if path in seen:
            continue
        bindings.append(binding)
        seen.add(path)
    return bindings


def merge_external_skill_bindings_into_selection_groups(
    selection_groups: dict[str, Any],
    external_skill_bindings: object,
) -> dict[str, list[dict[str, Any]]]:
    groups = normalize_documented_selection_groups(selection_groups)
    if not isinstance(external_skill_bindings, list):
        return groups

    bindings_by_path: dict[str, dict[str, Any]] = {}
    for raw_item in external_skill_bindings:
        if not isinstance(raw_item, dict):
            continue
        binding = _external_skill_binding_for_manifest(raw_item)
        if binding is None:
            continue
        bindings_by_path.setdefault(binding["path"], binding)
    if not bindings_by_path:
        return groups

    merged_groups: dict[str, list[dict[str, Any]]] = {key: list(groups.get(key, [])) for key in SELECTION_GROUP_KEYS}
    skills = merged_groups.get("skills", [])
    for index, item in enumerate(skills):
        path = str(item.get("path", "")).strip()
        binding = bindings_by_path.get(path)
        if binding is None:
            continue
        skills[index] = {
            **binding,
            **item,
            "source_path": binding["source_path"],
            "binding_kind": binding["binding_kind"],
            "source_kind": binding.get("source_kind", EXPLICIT_SKILL_SOURCE_KIND),
            "unit_type": "skill",
            "skip_skill_runtime_outputs": binding.get("skip_skill_runtime_outputs", True),
        }
    merged_groups["skills"] = skills
    return merged_groups


def explicit_skill_for_manifest(explicit_skill: dict[str, Any] | None) -> dict[str, Any] | None:
    if not explicit_skill:
        return None
    payload = {
        "path": str(explicit_skill.get("path", "")).strip(),
        "source_path": str(explicit_skill.get("source_path", "")).strip(),
        "binding_kind": EXPLICIT_SKILL_BINDING_KIND,
        "source_kind": EXPLICIT_SKILL_SOURCE_KIND,
        "unit_type": "skill",
        "name": str(explicit_skill.get("name", "")).strip(),
        "description": str(explicit_skill.get("description", "")).strip(),
        "skip_skill_runtime_outputs": bool(explicit_skill.get("skip_skill_runtime_outputs", True)),
    }
    return payload if payload["path"] and payload["source_path"] else None


def explicit_skill_from_manifest_extra(extra: object) -> dict[str, Any] | None:
    if not isinstance(extra, dict):
        return None
    payload = extra.get("explicit_skill")
    if not isinstance(payload, dict):
        return None
    return explicit_skill_for_manifest(payload)


__all__ = [
    "EXPLICIT_SKILL_BINDING_KIND",
    "EXPLICIT_SKILL_SOURCE_KIND",
    "external_skill_bindings_for_manifest",
    "explicit_skill_for_manifest",
    "explicit_skill_from_manifest_extra",
    "merge_external_skill_bindings_into_selection_groups",
    "merge_explicit_skill_into_selection_groups",
    "merge_explicit_skill_into_top_level_selections",
    "discovery_payload_from_explicit_skill",
    "resolve_explicit_skill",
]
