from __future__ import annotations

from pathlib import Path, PurePosixPath

from packaging._shared.contracts.path_shapes import (
    extract_bundle_command_display_path,
    extract_bundle_hook_display_path,
    extract_skill_dir_display_path,
    normalized_parts,
    rootless_skill_path,
    unit_type_from_path,
)
from packaging.configure.selection.unit_docs import selectable_unit_synopsis
from packaging._shared.contracts.selectable import normalize_text
from packaging.configure.runtimes.openclaw.selection_validation import (
    build_openclaw_selection_runtime_validation as _build_openclaw_selection_runtime_validation,
)
from packaging.configure.runtimes.openclaw.skill_metadata import (
    openclaw_skill_key_from_skill_dir,
)
from packaging.configure.runtimes.openclaw.workspace_common import (
    OPENCLAW_CRON_UNIT_PREFIX,
)


def extract_openclaw_plugin_display_path(display_path: str) -> str | None:
    parts = normalized_parts(display_path)
    if len(parts) >= 3 and parts[:2] == [".openclaw", "extensions"]:
        return PurePosixPath(*parts[:3]).as_posix()
    return None


def is_openclaw_plugin_embedded_skill_path(display_path: str) -> bool:
    parts = normalized_parts(display_path)
    return len(parts) >= 5 and parts[:2] == [".openclaw", "extensions"] and parts[3] == "skills"


def extract_selectable_unit_display_path(display_path: str, *, allow_bundle_units: bool = False) -> str | None:
    skill_path = extract_skill_dir_display_path(display_path)
    if skill_path:
        return skill_path
    if not allow_bundle_units:
        return None
    hook_path = extract_bundle_hook_display_path(display_path)
    if hook_path:
        return hook_path
    return extract_bundle_command_display_path(display_path)


def _openclaw_unit_type_from_path(relative_path: str, *, allow_bundle_units: bool = False) -> str:
    normalized = PurePosixPath(relative_path.rstrip("/")).as_posix()
    if allow_bundle_units:
        plugin_path = extract_openclaw_plugin_display_path(normalized)
        if plugin_path == normalized:
            return "openclaw_plugin"
    return unit_type_from_path(normalized, allow_bundle_units=allow_bundle_units)


def build_reference_tokens(relative_path: str, name: str, skill_key: str | None = None) -> list[str]:
    tokens: list[str] = []
    for token in (
        relative_path,
        rootless_skill_path(relative_path),
        f"@{name}",
        f"${name}",
        f"@{skill_key}" if skill_key else "",
        f"${skill_key}" if skill_key else "",
    ):
        if token and token not in tokens:
            tokens.append(token)
    return tokens


def _plugin_embedded_skill_entries(plugin_root: Path, plugin_display_path: str) -> list[dict]:
    skills_root = plugin_root / "skills"
    if not skills_root.is_dir():
        return []

    entries: list[dict] = []
    for child in sorted(skills_root.iterdir(), key=lambda item: item.name):
        if not child.is_dir():
            continue
        child_path = (PurePosixPath(plugin_display_path) / "skills" / child.name).as_posix()
        entries.append(
            {
                "name": child.name,
                "skill_key": openclaw_skill_key_from_skill_dir(child),
                "path": child_path,
            }
        )
    return entries


def _plugin_entry_synopsis(base_synopsis: str, embedded_skills: list[dict]) -> str:
    if not embedded_skills:
        return base_synopsis

    parts: list[str] = [base_synopsis] if base_synopsis else []
    for item in embedded_skills[:3]:
        parts.append(f"embedded skill: {item['name']}")
        synopsis = normalize_text(item.get("synopsis", ""))
        if synopsis:
            parts.append(synopsis)
    return "\n".join(part for part in parts if part)


def finalize_openclaw_selectable_entry(entry: dict, *, unit_path: Path) -> dict:
    unit_type = str(entry.get("unit_type", "skill")).strip() or "skill"
    if unit_type == "skill":
        skill_key = openclaw_skill_key_from_skill_dir(unit_path)
        if not skill_key:
            return entry
        finalized = dict(entry)
        finalized["skill_key"] = skill_key
        return finalized
    if unit_type != "openclaw_plugin":
        return entry

    display_path = str(entry.get("path", "")).strip()
    if not display_path:
        return entry

    embedded_skills = [
        {
            **item,
            "synopsis": selectable_unit_synopsis(unit_path / "skills" / item["name"], "skill"),
        }
        for item in _plugin_embedded_skill_entries(unit_path, display_path)
    ]
    if not embedded_skills:
        return entry

    reference_tokens: list[str] = []
    for item in embedded_skills:
        for token in build_reference_tokens(item["path"], item["name"], item.get("skill_key")):
            if token not in reference_tokens:
                reference_tokens.append(token)

    finalized = dict(entry)
    finalized["synopsis"] = _plugin_entry_synopsis(str(entry.get("synopsis", "")), embedded_skills)
    finalized["embedded_skills"] = [
        {
            "name": item["name"],
            "skill_key": item.get("skill_key", "") or item["name"],
            "path": item["path"],
        }
        for item in embedded_skills
    ]
    finalized["reference_tokens"] = reference_tokens
    return finalized


def classify_openclaw_directory_unit(unit_path: Path, display_path: str) -> tuple[str | None, str, bool]:
    normalized = PurePosixPath(display_path.rstrip("/")).as_posix()
    if not normalized or normalized == ".":
        return None, "unknown", True

    plugin_path = extract_openclaw_plugin_display_path(normalized)
    if plugin_path == normalized and (unit_path / "skills").is_dir():
        return normalized, "openclaw_plugin", True
    if is_openclaw_plugin_embedded_skill_path(normalized):
        return None, "suppressed", True

    selectable_path = extract_selectable_unit_display_path(normalized, allow_bundle_units=True)
    unit_type = _openclaw_unit_type_from_path(normalized, allow_bundle_units=True)
    if selectable_path == normalized and unit_type != "bundle_command":
        if unit_type == "skill":
            parts = [part for part in PurePosixPath(normalized).parts if part and part != "."]
            depth_after_skills = 0
            for index, part in enumerate(parts):
                if part == "skills":
                    depth_after_skills = len(parts) - index - 1
                    break
            if depth_after_skills == 1:
                if (unit_path / "SKILL.md").is_file():
                    return normalized, unit_type, True
                return normalized, unit_type, False
            if depth_after_skills > 1 and not (unit_path / "SKILL.md").is_file():
                return None, "unknown", True
        return normalized, unit_type, False
    return None, "unknown", True


def classify_openclaw_file_unit(display_path: str) -> tuple[str | None, str]:
    normalized = PurePosixPath(display_path.rstrip("/")).as_posix()
    if not normalized or normalized == ".":
        return None, "unknown"

    selectable_path = extract_selectable_unit_display_path(normalized, allow_bundle_units=True)
    unit_type = _openclaw_unit_type_from_path(normalized, allow_bundle_units=True)
    if selectable_path == normalized and unit_type == "bundle_command":
        return normalized, unit_type
    return None, "unknown"


def openclaw_owning_selectable_paths(display_path: str) -> tuple[str, ...]:
    normalized = PurePosixPath(display_path.rstrip("/")).as_posix()
    if not normalized or normalized == ".":
        return ()

    owning_paths: list[str] = []
    selectable_path = extract_selectable_unit_display_path(normalized, allow_bundle_units=True)
    if selectable_path and selectable_path not in owning_paths:
        owning_paths.append(selectable_path)
    plugin_path = extract_openclaw_plugin_display_path(normalized)
    if plugin_path and plugin_path not in owning_paths:
        owning_paths.append(plugin_path)
    return tuple(owning_paths)


def infer_openclaw_unit_type_from_path(display_path: str) -> str:
    normalized = PurePosixPath(display_path.rstrip("/")).as_posix()
    if not normalized or normalized == ".":
        return "unknown"
    if normalized.startswith(OPENCLAW_CRON_UNIT_PREFIX):
        return "cron"
    return _openclaw_unit_type_from_path(normalized, allow_bundle_units=True)


def build_openclaw_selection_runtime_validation(
    *,
    selected_paths: set[str],
    included_skills: list[dict],
) -> dict:
    return _build_openclaw_selection_runtime_validation(
        selected_paths=selected_paths,
        included_skills=included_skills,
    )


__all__ = [
    "build_reference_tokens",
    "build_openclaw_selection_runtime_validation",
    "classify_openclaw_directory_unit",
    "classify_openclaw_file_unit",
    "extract_openclaw_plugin_display_path",
    "extract_selectable_unit_display_path",
    "finalize_openclaw_selectable_entry",
    "infer_openclaw_unit_type_from_path",
    "is_openclaw_plugin_embedded_skill_path",
    "openclaw_owning_selectable_paths",
]
