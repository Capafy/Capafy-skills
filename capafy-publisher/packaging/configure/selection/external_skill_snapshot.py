from __future__ import annotations

import hashlib
from pathlib import Path

from packaging._shared.common.fs import relpath as fs_relpath
from packaging._shared.common.packaged_files import iter_packaged_files


def compute_skill_snapshot_digest(skill_root: Path) -> str:
    root = skill_root.expanduser().resolve()
    digest = hashlib.sha256()
    for path in iter_packaged_files(
        root,
        skip_skill_runtime_outputs=True,
    ):
        relpath = fs_relpath(path, root)
        digest.update(relpath.encode("utf-8"))
        digest.update(b"\0")
        try:
            raw = path.read_bytes()
        except OSError:
            raw = b""
        digest.update(hashlib.sha256(raw).digest())
        digest.update(b"\0")
    return digest.hexdigest()


__all__ = ["compute_skill_snapshot_digest"]
