from __future__ import annotations

import hashlib
from pathlib import Path

from packaging.common.fs import relpath as fs_relpath
from packaging.common.packaged_files import is_publisher_source_path, iter_packaged_files


def compute_publish_source_snapshot_digest(*, source_roots: object) -> str:
    if not isinstance(source_roots, (list, tuple)):
        raise ValueError("source_snapshot_roots must be an array")

    digest = hashlib.sha256()
    normalized_roots: list[tuple[str, Path]] = []
    for item in source_roots:
        if not isinstance(item, dict):
            raise ValueError("source_snapshot_roots items must be objects")
        group = str(item.get("group", "") or "").strip()
        logical_path = str(item.get("logical_path", "") or "").strip()
        source_path = str(item.get("source_path", "") or "").strip()
        if not group or not logical_path or not source_path:
            raise ValueError("source_snapshot_roots items require group, logical_path, and source_path")
        root = Path(source_path).expanduser()
        if not root.is_absolute():
            raise ValueError(f"source snapshot path must be absolute: {source_path}")
        if is_publisher_source_path(root):
            raise ValueError(f"publisher source cannot be used for snapshot: {source_path}")
        normalized_roots.append((f"{group}:{logical_path}", root))

    for label, root in sorted(normalized_roots, key=lambda item: (item[0], str(item[1]))):
        digest.update(label.encode("utf-8")); digest.update(b"\0")
        if root.is_file():
            paths, base = [root], root.parent
        elif root.is_dir():
            paths, base = (
                [
                    path
                    for path in iter_packaged_files(root)
                    if not is_publisher_source_path(path)
                ],
                root,
            )
        else:
            digest.update(b"<missing>\0")
            continue
        for path in sorted(paths):
            try:
                raw, relative = path.read_bytes(), fs_relpath(path, base)
            except OSError as exc:
                raise ValueError(f"failed to read publish source snapshot path: {path}") from exc
            digest.update(relative.encode("utf-8")); digest.update(b"\0")
            digest.update(hashlib.sha256(raw).digest()); digest.update(b"\0")
    return digest.hexdigest()


__all__ = [
    "compute_publish_source_snapshot_digest",
]
