from __future__ import annotations

from pathlib import PurePosixPath


HOME_RUNTIME_PACKAGED_ROOTS = frozenset({
    ".agents",
    ".claude",
    ".codex",
    ".config",
    ".openclaw",
    "workspace_documents",
})


def _normalized_packaged_path(packaged_path: str) -> str:
    return PurePosixPath(str(packaged_path or "").replace("\\", "/").lstrip("/")).as_posix()


def build_packaged_runtime_ref(packaged_path: str) -> str:
    normalized = _normalized_packaged_path(packaged_path)
    if not normalized or normalized == ".":
        return "~"
    return f"~/{normalized}"


def is_packaged_runtime_ref(value: str) -> bool:
    normalized = str(value or "").strip().strip("'\"").replace("\\", "/")
    if not normalized.startswith("~/"):
        return False
    runtime_path = normalized[2:]
    if not runtime_path:
        return False
    if runtime_path == "workspace":
        return True
    first_part = PurePosixPath(runtime_path).parts[0]
    if first_part in HOME_RUNTIME_PACKAGED_ROOTS:
        return True
    return False


def build_manifest_packaged_ref(source_path: str, packaged_path: str) -> str:
    normalized = _normalized_packaged_path(packaged_path)
    if not normalized or normalized == ".":
        return packaged_path
    parts = PurePosixPath(normalized).parts
    if not parts or parts[0] not in HOME_RUNTIME_PACKAGED_ROOTS:
        return packaged_path
    sep = "\\" if "\\" in str(source_path or "") else "/"
    return "~" + sep + sep.join(parts)


def build_packaged_path_refs(manifest_payload: dict) -> dict[str, str]:
    refs: dict[str, str] = {}
    items = manifest_payload.get("workspace_documents")
    if not isinstance(items, list):
        return refs
    for item in items:
        if not isinstance(item, dict):
            continue
        packaged_path = str(item.get("packaged_path", "") or "").strip()
        if not packaged_path:
            continue
        for key in ("resolved_source_path", "source_path"):
            source_path = str(item.get(key, "") or "").strip()
            if source_path:
                refs.setdefault(source_path, build_manifest_packaged_ref(source_path, packaged_path))
    return refs


def public_source_path_item(item: object) -> object:
    if not isinstance(item, dict):
        return item
    public_item = dict(item)
    for key in ("source_path", "resolved_source_path", "source_root"):
        public_item.pop(key, None)
    return public_item


__all__ = [
    "HOME_RUNTIME_PACKAGED_ROOTS",
    "build_manifest_packaged_ref",
    "build_packaged_path_refs",
    "build_packaged_runtime_ref",
    "is_packaged_runtime_ref",
    "public_source_path_item",
]
