from __future__ import annotations

from pathlib import Path, PurePosixPath

from packaging._shared.contracts.selectable import INSTRUCTION_DOC_BASENAMES, INSTRUCTION_DOC_SUFFIXES




SUSPICIOUS_SKILL_BASENAMES = {
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
}


SUSPICIOUS_SKILL_SUFFIXES = (
    ".key",
    ".p12",
    ".pfx",
    ".ppk",
    ".keychain",
    ".keychain-db",
    ".keystore",
    ".jks",
    ".kdb",
    ".kdbx",
    ".kwallet",
    ".agilekeychain",
    ".ovpn",
)


BUNDLE_COMMAND_SUFFIXES = (".md", ".markdown", ".mdx", ".txt")


SKILL_UNIT_TYPE = "skill"
PLUGIN_UNIT_TYPE = "plugin"
OPENCLAW_PLUGIN_UNIT_TYPE = "openclaw_plugin"
BUNDLE_COMMAND_UNIT_TYPE = "bundle_command"
BUNDLE_HOOK_PACK_UNIT_TYPE = "bundle_hook_pack"
CRON_UNIT_TYPE = "cron"
UNKNOWN_UNIT_TYPE = "unknown"



PLUGIN_UNIT_TYPES = frozenset(
    {
        PLUGIN_UNIT_TYPE,
        OPENCLAW_PLUGIN_UNIT_TYPE,
        BUNDLE_COMMAND_UNIT_TYPE,
        BUNDLE_HOOK_PACK_UNIT_TYPE,
    }
)


CRON_UNIT_TYPES = frozenset({CRON_UNIT_TYPE})


def is_plugin_unit_type(unit_type: str) -> bool:
    return str(unit_type).strip() in PLUGIN_UNIT_TYPES


def is_cron_unit_type(unit_type: str) -> bool:
    return str(unit_type).strip() in CRON_UNIT_TYPES


def normalized_parts(display_path: str) -> list[str]:
    pure = PurePosixPath(display_path.rstrip("/"))
    return [part for part in pure.parts if part and part != "."]


def _skills_segment_index(parts: list[str]) -> int | None:
    for index, part in enumerate(parts):
        if part == "skills" and index + 1 < len(parts):
            return index
    return None


def _looks_like_file_path(parts: list[str]) -> bool:
    if not parts:
        return False
    name = parts[-1]
    lowered = name.lower()
    if name in INSTRUCTION_DOC_BASENAMES:
        return True
    return lowered.endswith(INSTRUCTION_DOC_SUFFIXES)


def _candidate_skill_paths(display_path: str) -> list[str]:
    parts = normalized_parts(display_path)
    skills_index = _skills_segment_index(parts)
    if skills_index is None:
        return []

    end = len(parts) - 1 if _looks_like_file_path(parts) else len(parts)
    if end <= skills_index + 1:
        return []

    candidates: list[str] = []
    for candidate_end in range(skills_index + 2, end + 1):
        candidates.append(PurePosixPath(*parts[:candidate_end]).as_posix())
    return candidates


def _skill_depth_after_root(display_path: str) -> int:
    parts = normalized_parts(display_path)
    skills_index = _skills_segment_index(parts)
    if skills_index is None:
        return 0
    return len(parts) - skills_index - 1


def suspicious_skill_file_reason(relpath: str) -> str | None:
    pure = PurePosixPath(relpath)
    lowered = relpath.lower()
    basename = pure.name.lower()
    if basename in SUSPICIOUS_SKILL_BASENAMES:
        return f"contains sensitive credential file: {relpath}"
    for suffix in SUSPICIOUS_SKILL_SUFFIXES:
        if lowered.endswith(suffix):
            return f"contains sensitive credential file: {relpath}"
    return None


def extract_skill_dir_display_path(display_path: str) -> str | None:
    candidates = _candidate_skill_paths(display_path)
    if not candidates:
        return None
    return candidates[0]


def extract_bundle_command_display_path(display_path: str) -> str | None:
    parts = normalized_parts(display_path)
    if "extensions" not in parts:
        return None
    if len(parts) >= 2 and parts[-2] == "commands":
        suffix = PurePosixPath(parts[-1]).suffix.lower()
        if suffix in BUNDLE_COMMAND_SUFFIXES:
            return PurePosixPath(*parts).as_posix()
    if len(parts) >= 3 and parts[-3:] and parts[-3] == ".cursor" and parts[-2] == "commands":
        suffix = PurePosixPath(parts[-1]).suffix.lower()
        if suffix in BUNDLE_COMMAND_SUFFIXES:
            return PurePosixPath(*parts).as_posix()
    return None


def extract_bundle_hook_display_path(display_path: str) -> str | None:
    parts = normalized_parts(display_path)
    if "extensions" not in parts:
        return None
    for index, part in enumerate(parts):
        if part == "hooks" and index + 1 < len(parts):
            return PurePosixPath(*parts[: index + 2]).as_posix()
    return None


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


def classify_basic_selectable_directory(unit_path: Path, display_path: str) -> tuple[str | None, str, bool]:
    normalized = PurePosixPath(display_path.rstrip("/")).as_posix()
    if not normalized or normalized == ".":
        return None, "unknown", True

    candidate_paths = _candidate_skill_paths(normalized)
    if normalized not in candidate_paths:
        return None, "unknown", True

    depth_after_skills = _skill_depth_after_root(normalized)
    has_skill_md = (unit_path / "SKILL.md").is_file()

    if depth_after_skills == 1:
        if has_skill_md:
            return normalized, SKILL_UNIT_TYPE, True
        for nested_skill_md in unit_path.rglob("SKILL.md"):
            if nested_skill_md.parent != unit_path:
                return None, "unknown", True
        return normalized, SKILL_UNIT_TYPE, False

    if depth_after_skills > 1:
        if has_skill_md:
            return normalized, SKILL_UNIT_TYPE, False
        return None, "unknown", True

    if has_skill_md:
        return normalized, SKILL_UNIT_TYPE, False
    return None, "unknown", True


def classify_basic_selectable_file(display_path: str) -> tuple[str | None, str]:
    normalized = PurePosixPath(display_path.rstrip("/")).as_posix()
    if not normalized or normalized == ".":
        return None, "unknown"
    return None, "unknown"


def basic_owning_selectable_paths(display_path: str) -> tuple[str, ...]:
    normalized = PurePosixPath(display_path.rstrip("/")).as_posix()
    if not normalized or normalized == ".":
        return ()
    candidates = _candidate_skill_paths(normalized)
    return tuple(candidates)


def basic_owning_plugin_paths(display_path: str) -> tuple[str, ...]:
    del display_path
    return ()


def basic_allowed_skill_root_prefixes(display_prefix: str) -> set[str]:
    normalized = PurePosixPath(display_prefix.rstrip("/")).as_posix()
    if not normalized or normalized == ".":
        return set()

    allowed: set[str] = set()
    if normalized == "skills" or normalized.endswith("/skills"):
        allowed.add(normalized)

    parts = [part for part in PurePosixPath(normalized).parts if part and part != "."]
    if parts and parts[-1] == "workspace":
        for suffix in ("skills", ".agents/skills", ".claude/skills"):
            allowed.add(f"{normalized}/{suffix}")
    return allowed


def unit_type_from_path(relative_path: str, *, allow_bundle_units: bool = False) -> str:
    if extract_skill_dir_display_path(relative_path):
        return SKILL_UNIT_TYPE
    if allow_bundle_units:
        if extract_bundle_command_display_path(relative_path):
            return BUNDLE_COMMAND_UNIT_TYPE
        if extract_bundle_hook_display_path(relative_path):
            return BUNDLE_HOOK_PACK_UNIT_TYPE
    return UNKNOWN_UNIT_TYPE


def rootless_skill_path(relative_path: str) -> str | None:
    marker = "/skills/"
    if marker not in relative_path:
        return None
    _, suffix = relative_path.split(marker, 1)
    if not suffix:
        return None
    return f"skills/{suffix}"
