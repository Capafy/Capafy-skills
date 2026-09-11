from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath

from packaging.common.fs import is_within
from packaging.common.home import safe_expanduser_path
from packaging.common.instruction_docs import is_instruction_doc
from packaging.runtime.profiles import load_profile


OPENCLAW_ROOT = safe_expanduser_path("~/.openclaw")
AGENTS_SKILLS_ROOT = safe_expanduser_path("~/.agents/skills")
OPENCLAW_CONFIG_PATH_ENV = "OPENCLAW_CONFIG_PATH"
OPENCLAW_STATE_DIR_ENV = "OPENCLAW_STATE_DIR"
WORKSPACE_SKILL_SUBDIRS = ("skills", ".claude/skills", ".agents/skills")
PACKAGED_WORKSPACE_NAME = "workspace"


def resolve_openclaw_config_source(
    *,
    openclaw_root: Path = OPENCLAW_ROOT,
) -> Path:
    configured = str(os.environ.get(OPENCLAW_CONFIG_PATH_ENV, "") or "").strip()
    if configured:
        return safe_expanduser_path(configured)

    state_dir = str(os.environ.get(OPENCLAW_STATE_DIR_ENV, "") or "").strip()
    if state_dir:
        return safe_expanduser_path(state_dir) / "openclaw.json"

    return safe_expanduser_path(openclaw_root) / "openclaw.json"


def resolve_openclaw_state_root(
    *,
    openclaw_root: Path = OPENCLAW_ROOT,
) -> Path:
    configured = str(os.environ.get(OPENCLAW_STATE_DIR_ENV, "") or "").strip()
    if configured:
        return safe_expanduser_path(configured)
    return safe_expanduser_path(openclaw_root)


def _openclaw_workspace_candidate(workspace_reference: str, *, openclaw_root: Path) -> Path:
    normalized = str(workspace_reference or "").strip()
    if not normalized:
        raise ValueError("runtime_dir is required")
    candidate = safe_expanduser_path(normalized)
    if candidate.is_absolute():
        return candidate

    parts = candidate.parts
    openclaw_base = resolve_openclaw_state_root(openclaw_root=openclaw_root)
    if parts and parts[0] == ".openclaw":
        return openclaw_base.joinpath(*parts[1:])
    return openclaw_base / candidate


def validate_openclaw_workspace_root(workspace_root: Path, *, openclaw_root: Path = OPENCLAW_ROOT) -> Path:
    resolved = safe_expanduser_path(workspace_root).resolve(strict=False)
    if not resolved.is_dir():
        raise ValueError(f"OpenClaw runtime_dir workspace does not exist: {workspace_root}")
    if (resolved / "SKILL.md").is_file():
        raise ValueError(
            "OpenClaw runtime_dir must be the workspace root, not a single skill directory: "
            f"{workspace_root}"
        )
    openclaw_base = resolve_openclaw_state_root(openclaw_root=openclaw_root).resolve(strict=False)
    config_source = resolve_openclaw_config_source(openclaw_root=openclaw_root)
    if not config_source.is_file():
        raise ValueError(f"OpenClaw root is missing openclaw.json: {config_source}")
    try:
        relative = resolved.relative_to(openclaw_base)
    except ValueError as exc:
        raise ValueError(
            f"OpenClaw runtime_dir must be an OpenClaw workspace under {openclaw_base}, for example "
            f"{openclaw_base / 'workspace'}"
        ) from exc
    first = relative.parts[0] if relative.parts else ""
    if len(relative.parts) != 1 or not first.startswith("workspace"):
        raise ValueError(
            "OpenClaw runtime_dir must be an OpenClaw workspace directory, for example ~/.openclaw/workspace"
        )
    return resolved


def resolve_openclaw_workspace_runtime_dir(
    runtime_dir: str,
    *,
    openclaw_root: Path = OPENCLAW_ROOT,
) -> Path:
    workspace_root = _openclaw_workspace_candidate(runtime_dir, openclaw_root=openclaw_root)
    return validate_openclaw_workspace_root(workspace_root, openclaw_root=openclaw_root)


def _configured_memory_paths(openclaw_root: Path) -> list[str]:
    config_path = openclaw_root / "openclaw.json"
    if not config_path.is_file():
        return []
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []

    paths: list[str] = []

    def append_path_items(items: object) -> None:
        if not isinstance(items, list):
            return
        for item in items:
            if isinstance(item, str):
                normalized = item.strip()
            elif isinstance(item, dict):
                normalized = str(item.get("path", "") or "").strip()
            else:
                normalized = ""
            if normalized:
                paths.append(normalized)

    memory = payload.get("memory")
    if isinstance(memory, dict):
        qmd = memory.get("qmd")
        if isinstance(qmd, dict):
            append_path_items(qmd.get("paths"))
    return paths


def _add_configured_workspace_memory_paths(
    allowed: set[str],
    workspace_root: Path,
    *,
    packaged_workspace_prefix: str,
) -> None:
    workspace_resolved = workspace_root.resolve(strict=False)
    for raw_path in _configured_memory_paths(workspace_root.parent):
        candidate = safe_expanduser_path(raw_path)
        if not candidate.is_absolute():
            candidate = workspace_root / candidate
        resolved = candidate.resolve(strict=False)
        if not is_within(resolved, workspace_resolved):
            continue
        try:
            relative = resolved.relative_to(workspace_resolved)
        except ValueError:
            continue
        if not relative.parts:
            continue
        allowed.add(f"{packaged_workspace_prefix}/{relative.as_posix()}")


def _profile_workspace_root_docs(profile: Optional[dict] = None) -> tuple[str, ...]:
    result: list[str] = []
    resolved_profile = profile if profile is not None else load_profile("openclaw")
    for file_spec in resolved_profile.get("fixed_scan_files", []):
        if not isinstance(file_spec, dict):
            continue
        if str(file_spec.get("base", "") or "").strip() != "runtime_dir":
            continue
        path = PurePosixPath(str(file_spec.get("path", "") or "").strip())
        if len(path.parts) != 1 or path.name in {"", ".", ".."}:
            continue
        if not is_instruction_doc(path.name):
            continue
        if path.name not in result:
            result.append(path.name)
    return tuple(result)


def build_workspace_allowlist(
    workspace_root: Path,
    *,
    packaged_workspace_prefix: str,
    profile: Optional[dict] = None,
) -> set[str]:
    allowed: set[str] = set()

    for filename in _profile_workspace_root_docs(profile):
        if (workspace_root / filename).is_file():
            allowed.add(f"{packaged_workspace_prefix}/{filename}")

    for subdir in WORKSPACE_SKILL_SUBDIRS:
        if (workspace_root / subdir).is_dir():
            allowed.add(f"{packaged_workspace_prefix}/{subdir}")

    _add_configured_workspace_memory_paths(
        allowed,
        workspace_root,
        packaged_workspace_prefix=packaged_workspace_prefix,
    )
    return allowed


__all__ = [
    "AGENTS_SKILLS_ROOT",
    "OPENCLAW_CONFIG_PATH_ENV",
    "OPENCLAW_ROOT",
    "OPENCLAW_STATE_DIR_ENV",
    "PACKAGED_WORKSPACE_NAME",
    "build_workspace_allowlist",
    "resolve_openclaw_config_source",
    "resolve_openclaw_state_root",
    "resolve_openclaw_workspace_runtime_dir",
    "validate_openclaw_workspace_root",
]
