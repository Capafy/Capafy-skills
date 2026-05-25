from __future__ import annotations
from typing import Optional

from pathlib import Path, PurePosixPath

from packaging._shared.contracts.selectable import is_absolute_like_path, normalize_text
from packaging._shared.runtimes.contracts import call_optional_target_hook
from packaging.configure.selection.confirmed_paths import packaged_fallback_path


ROOT_PREFIXES = (
    "workspace",
    ".agents",
    ".claude",
    ".codex",
    ".config",
)


def resolve_logical_source_path(
    logical_path: str,
    *,
    workspace_root: Optional[Path],
    target_name: Optional[str],
) -> Path:
    from packaging.runtimes import DEFAULT_TARGET, get_target, resolve_target_request

    normalized = normalize_text(logical_path)
    if not normalized:
        raise ValueError("confirmed workspace document path must not be empty")
    if is_absolute_like_path(normalized):
        candidate = Path(normalized).expanduser()
        if not candidate.exists():
            raise ValueError(f"confirmed workspace document does not exist: {normalized}")
        return candidate.resolve(strict=True)

    resolved_target = resolve_target_request(target_name or DEFAULT_TARGET).resolved_name
    target = get_target(resolved_target)
    prefix_map: dict[str, Optional[Path]] = {
        "workspace": workspace_root,
        ".agents": (Path.home() / ".agents").expanduser(),
        ".claude": (Path.home() / ".claude").expanduser(),
        ".codex": (Path.home() / ".codex").expanduser(),
        ".config": (Path.home() / ".config").expanduser(),
    }
    prefix_map.update(
        call_optional_target_hook(
            target,
            "confirmed_workspace_document_prefix_roots",
            default={},
        )
    )
    pure = PurePosixPath(normalized)
    root_name = pure.parts[0] if pure.parts else ""
    base_root = prefix_map.get(root_name)
    if base_root is None:
        if workspace_root is None:
            raise ValueError(f"cannot resolve confirmed workspace document: {normalized}")
        candidate = workspace_root / normalized
    else:
        if not isinstance(base_root, Path):
            raise ValueError(f"workspace is required to resolve confirmed workspace document: {normalized}")
        suffix = PurePosixPath(*pure.parts[1:]).as_posix() if len(pure.parts) > 1 else ""
        candidate = base_root / suffix if suffix else base_root
    if not candidate.exists():
        raise ValueError(f"confirmed workspace document does not exist: {normalized}")
    return candidate.resolve(strict=True)


def target_relative_packaged_path(logical_path: str, *, target_name: Optional[str]) -> tuple[str, bool]:
    from packaging.runtimes import DEFAULT_TARGET, get_target, resolve_target_request

    normalized = PurePosixPath(logical_path.rstrip("/")).as_posix()
    if not normalized:
        return normalized, False

    resolved_target = resolve_target_request(target_name or DEFAULT_TARGET).resolved_name
    target = get_target(resolved_target)
    rewritten = call_optional_target_hook(
        target,
        "rewrite_confirmed_workspace_document_packaged_path",
        normalized,
        default=normalized,
    )
    rewritten = normalize_text(rewritten) or normalized
    return rewritten, rewritten != normalized


def preserved_logical_root_prefixes(*, target_name: Optional[str]) -> set[str]:
    from packaging.runtimes import DEFAULT_TARGET, get_target, resolve_target_request

    roots = set(ROOT_PREFIXES)
    resolved_target = resolve_target_request(target_name or DEFAULT_TARGET).resolved_name
    target = get_target(resolved_target)
    target_roots = call_optional_target_hook(
        target,
        "confirmed_workspace_document_prefix_roots",
        default={},
    )
    if isinstance(target_roots, dict):
        roots.update(str(key).strip() for key in target_roots.keys() if str(key).strip())
    return roots


def packaged_path_for_entry(
    logical_path: str,
    source_path: Path,
    *,
    target_name: Optional[str],
    agent_type: str,
    used_paths: set[str],
) -> str:
    normalized, target_rewritten = target_relative_packaged_path(logical_path, target_name=target_name)
    if target_rewritten and not is_absolute_like_path(normalized):
        used_paths.add(normalized)
        return normalized
    if agent_type != "download" and not is_absolute_like_path(normalized):
        first_part = PurePosixPath(normalized).parts[0] if normalized else ""
        if first_part in preserved_logical_root_prefixes(target_name=target_name):
            used_paths.add(normalized)
            return normalized

    return packaged_fallback_path(normalized, source_path, used_paths=used_paths)


__all__ = [
    "ROOT_PREFIXES",
    "packaged_path_for_entry",
    "preserved_logical_root_prefixes",
    "resolve_logical_source_path",
    "target_relative_packaged_path",
]
