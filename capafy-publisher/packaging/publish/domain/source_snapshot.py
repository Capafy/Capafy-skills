from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from packaging.common.fs import iter_workspace_files, relpath as fs_relpath
from packaging.common.packaged_files import is_publisher_source_path


def compute_publish_source_snapshot_digest(*, runtime_dir: str, latest_state: Any, manifest: Any) -> str:
    roots: dict[str, Path] = {}

    def add_root(label: str, raw_path: object) -> None:
        value = str(raw_path or "").strip()
        if value:
            path = Path(value).expanduser().resolve(strict=False)
            roots.setdefault(f"{label}:{path}", path)

    add_root("runtime_dir", runtime_dir)
    extra = manifest.extra if isinstance(getattr(manifest, "extra", None), dict) else {}
    explicit_skill = extra.get("explicit_skill")
    if isinstance(explicit_skill, dict):
        add_root("explicit_skill", explicit_skill.get("source_path") or explicit_skill.get("source_root"))
    bindings = extra.get("external_skill_bindings")
    if isinstance(bindings, list):
        for binding in bindings:
            if isinstance(binding, dict):
                add_root(f"external_skill:{binding.get('path', '')}", binding.get("source_path"))
    selection_groups = getattr(latest_state, "selection_groups", {})
    if isinstance(selection_groups, dict):
        for group_name, items in selection_groups.items():
            if not isinstance(items, list):
                continue
            for index, item in enumerate(items):
                if isinstance(item, dict):
                    add_root(f"selection:{group_name}:{index}", item.get("source_path") or item.get("source_root"))

    digest = hashlib.sha256()
    for label, root in sorted(roots.items()):
        digest.update(label.encode("utf-8")); digest.update(b"\0")
        if is_publisher_source_path(root):
            continue
        if root.is_file():
            paths, base = [root], root.parent
        elif root.is_dir():
            paths, base = (
                [path for path in iter_workspace_files(root, skip_system=True) if not is_publisher_source_path(path)],
                root,
            )
        else:
            digest.update(b"<missing>\0")
            continue
        for path in sorted(paths):
            try:
                raw, relative = path.read_bytes(), fs_relpath(path, base)
            except OSError:
                raw, relative = b"", "<unreadable>"
            digest.update(relative.encode("utf-8")); digest.update(b"\0")
            digest.update(hashlib.sha256(raw).digest()); digest.update(b"\0")
    return digest.hexdigest()


__all__ = ["compute_publish_source_snapshot_digest"]
