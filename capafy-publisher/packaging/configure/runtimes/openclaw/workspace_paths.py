from __future__ import annotations

import json
from pathlib import Path

from packaging._shared.common.fs import is_within
from packaging._shared.common.home import safe_expanduser_path
from packaging.configure.runtimes.openclaw.workspace_common import (
    OPENCLAW_ROOT,
    WORKSPACE_ROOT_DOCS,
    WORKSPACE_SKILL_SUBDIRS,
)


def _openclaw_workspace_candidate(workspace_reference: str, *, openclaw_root: Path) -> Path:
    normalized = str(workspace_reference or "").strip()
    if not normalized:
        raise ValueError("runtime_dir is required")
    candidate = safe_expanduser_path(normalized)
    if candidate.is_absolute():
        return candidate

    parts = candidate.parts
    openclaw_base = safe_expanduser_path(openclaw_root)
    if parts and parts[0] == ".openclaw":
        return openclaw_base.parent.joinpath(*parts)
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
    openclaw_base = safe_expanduser_path(openclaw_root).resolve(strict=False)
    if not (openclaw_base / "openclaw.json").is_file():
        raise ValueError(f"OpenClaw root is missing openclaw.json: {openclaw_base / 'openclaw.json'}")
    try:
        relative = resolved.relative_to(openclaw_base)
    except ValueError as exc:
        raise ValueError(
            "OpenClaw runtime_dir must be an OpenClaw workspace under ~/.openclaw, for example "
            "~/.openclaw/workspace"
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


def _compute_packaged_workspace_name(
    workspace_root: Path,
    openclaw_root: Path,
) -> str:
    candidate_name = workspace_root.name.strip()
    if candidate_name.startswith("workspace"):
        return candidate_name

    openclaw_base = safe_expanduser_path(openclaw_root).resolve(strict=False)
    try:
        relative = workspace_root.resolve(strict=False).relative_to(openclaw_base)
    except ValueError:
        return "workspace"

    parts = relative.parts
    if parts:
        first = str(parts[0]).strip()
        if first.startswith("workspace"):
            return first
    return "workspace"


def packaged_workspace_name(
    workspace_name: str,
    *,
    openclaw_root: Path = OPENCLAW_ROOT,
) -> str:
    workspace_root = resolve_openclaw_workspace_runtime_dir(workspace_name, openclaw_root=openclaw_root)
    return _compute_packaged_workspace_name(
        workspace_root=workspace_root,
        openclaw_root=openclaw_root,
    )


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


def build_workspace_allowlist(
    workspace_root: Path,
    *,
    packaged_workspace_prefix: str,
) -> set[str]:
    allowed: set[str] = set()

    for filename in WORKSPACE_ROOT_DOCS:
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
    "build_workspace_allowlist",
    "packaged_workspace_name",
    "resolve_openclaw_workspace_runtime_dir",
    "validate_openclaw_workspace_root",
]
