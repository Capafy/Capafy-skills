from __future__ import annotations
from typing import Optional

import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

from packaging._shared.common.final_zip_files import collect_final_zip_entries
from packaging._shared.policies.package_invariants import validate_no_packaged_local_path_violations


_TEXT_APPEND_SUFFIXES = {".md", ".markdown", ".mdx", ".txt"}


def _json_dedupe_key(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _merge_json_values(base: object, overlay: object) -> object:
    if isinstance(base, dict) and isinstance(overlay, dict):
        merged = dict(base)
        for raw_key, value in overlay.items():
            key = str(raw_key)
            if key in merged:
                merged[key] = _merge_json_values(merged[key], value)
            else:
                merged[key] = value
        return merged
    if isinstance(base, list) and isinstance(overlay, list):
        merged_items = list(base)
        seen = {_json_dedupe_key(item) for item in merged_items}
        for item in overlay:
            marker = _json_dedupe_key(item)
            if marker in seen:
                continue
            merged_items.append(item)
            seen.add(marker)
        return merged_items
    return overlay


def _merge_json_files(paths: list[Path], archive_path: str) -> bytes:
    merged: Optional[object] = None
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"bundle JSON path collision cannot be merged for {archive_path}: "
                f"{path} parse failed: {exc}"
            ) from exc
        if merged is None:
            merged = payload
        else:
            merged = _merge_json_values(merged, payload)
    return (json.dumps(merged, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _append_text_files(paths: list[Path], archive_path: str) -> bytes:
    merged = ""
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"bundle text path collision cannot be merged for {archive_path}: "
                f"{path} is not UTF-8"
            ) from exc
        if not text:
            continue
        if not merged:
            merged = text
            continue
        if not merged.endswith("\n"):
            merged += "\n"
        if not merged.endswith("\n\n"):
            merged += "\n"
        merged += text.lstrip("\n")
    if merged and not merged.endswith("\n"):
        merged += "\n"
    return merged.encode("utf-8")


def _merged_file_payload(paths: list[Path], archive_path: str) -> bytes:
    suffix = PurePosixPath(archive_path).suffix.lower()
    if suffix == ".json":
        return _merge_json_files(paths, archive_path)
    if suffix in _TEXT_APPEND_SUFFIXES:
        return _append_text_files(paths, archive_path)
    raise ValueError(f"bundle path collision cannot be merged automatically: {archive_path}")


def _sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_bundle_archive(
    staging_root: Path,
    output_path: Path,
    *,
    exclude_paths: Optional[set[str]] = None,
    exclude_prefixes: tuple[str, ...] = (),
) -> dict:
    if output_path.suffix.lower() != ".zip":
        raise ValueError(f"bundle output path must end with .zip: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    validate_no_packaged_local_path_violations(
        staging_root,
        exclude_paths=exclude_paths,
        exclude_prefixes=exclude_prefixes,
    )

    entries = collect_final_zip_entries(
        staging_root,
        exclude_paths=exclude_paths,
        exclude_prefixes=exclude_prefixes,
    )

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for directory in sorted(entries.archive_directories):
            archive.writestr(directory.rstrip("/") + "/", "")
        for archive_path in sorted(entries.files_by_archive_path):
            source_paths = list(entries.files_by_archive_path[archive_path])
            if len(source_paths) == 1:
                archive.write(source_paths[0], arcname=archive_path)
                continue
            archive.writestr(archive_path, _merged_file_payload(source_paths, archive_path))

    return {
        "bundle_path": str(output_path),
        "size_bytes": output_path.stat().st_size,
        "sha256": _sha256_of_file(output_path),
        "file_count": len(entries.files_by_archive_path),
    }


__all__ = [
    "build_bundle_archive",
]
