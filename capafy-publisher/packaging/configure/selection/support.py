from __future__ import annotations
from typing import Optional

from pathlib import Path

from packaging._shared.contracts.selectable import normalize_text


def classify_selectable_directory(target, unit_path: Path, display_path: str) -> tuple[Optional[str], str, bool]:
    from packaging._shared.contracts.path_shapes import classify_basic_selectable_directory
    from packaging._shared.runtimes.contracts import call_optional_target_hook

    return call_optional_target_hook(
        target,
        "classify_selectable_directory",
        unit_path,
        display_path,
        default=classify_basic_selectable_directory(unit_path, display_path),
    )


def finalize_selectable_entry(target, entry: dict, *, unit_path: Path) -> dict:
    if target is None:
        return entry

    from packaging._shared.runtimes.contracts import call_optional_target_hook

    return call_optional_target_hook(
        target,
        "finalize_selectable_entry",
        entry,
        unit_path=unit_path,
        default=entry,
    )


def resolve_workspace_root(
    *,
    workspace: Optional[str],
    target_name: Optional[str] = None,
) -> Optional[Path]:
    from packaging.runtimes import DEFAULT_TARGET, get_target, resolve_target_request
    normalized_workspace = normalize_text(workspace)
    if not normalized_workspace:
        return None

    active_target = resolve_target_request(target_name or DEFAULT_TARGET).resolved_name

    try:
        target = get_target(active_target)
    except ValueError:
        return None

    from packaging._shared.runtimes.contracts import call_optional_target_hook

    resolved = call_optional_target_hook(
        target,
        "resolve_workspace_reference",
        normalized_workspace,
        default=None,
    )
    if resolved is not None:
        return resolved

    fallback = Path(normalized_workspace).expanduser()
    if not fallback.is_dir():
        return None
    return fallback.resolve(strict=False)
