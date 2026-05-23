from __future__ import annotations

import os
from pathlib import Path


def build_unit_metadata(
    skill_dir: Path,
    unit_type: str = "skill",
    *,
    target=None,
) -> dict:
    from packaging._shared.common.fs import relpath
    from packaging._shared.contracts.path_shapes import suspicious_skill_file_reason
    from packaging.configure.selection.unit_docs import (
        missing_primary_doc_reason,
        primary_instruction_doc,
        selectable_unit_description,
        selectable_unit_name,
        selectable_unit_synopsis,
    )

    primary_doc = primary_instruction_doc(skill_dir, unit_type, target=target)
    has_primary_doc = primary_doc is not None

    file_count = 0
    size_bytes = 0
    suspicious_reasons: list[str] = []
    seen_reasons: set[str] = set()

    missing_reason = missing_primary_doc_reason(unit_type)
    if missing_reason and not has_primary_doc:
        suspicious_reasons.append(missing_reason)
        seen_reasons.add(missing_reason)

    if skill_dir.is_file():
        file_count = 1
        try:
            size_bytes = skill_dir.stat().st_size
        except OSError:
            size_bytes = 0
        reason = suspicious_skill_file_reason(skill_dir.name)
        if reason and reason not in seen_reasons:
            suspicious_reasons.append(reason)
            seen_reasons.add(reason)
    else:
        for current, _, filenames in os.walk(skill_dir, topdown=True):
            current_path = Path(current)
            for filename in sorted(filenames):
                file_path = current_path / filename
                file_count += 1
                try:
                    size_bytes += file_path.stat().st_size
                except OSError:
                    continue
                file_relpath = relpath(file_path, skill_dir)
                reason = suspicious_skill_file_reason(file_relpath)
                if reason and reason not in seen_reasons:
                    suspicious_reasons.append(reason)
                    seen_reasons.add(reason)

    if file_count > 200:
        reason = f"Large file count: {file_count}"
        suspicious_reasons.append(reason)
        seen_reasons.add(reason)
    if size_bytes > 5 * 1024 * 1024:
        reason = f"Large size: {size_bytes} bytes"
        suspicious_reasons.append(reason)
        seen_reasons.add(reason)

    name = selectable_unit_name(skill_dir, unit_type, target=target)
    description = selectable_unit_description(skill_dir, unit_type, target=target)
    synopsis = selectable_unit_synopsis(skill_dir, unit_type, target=target)

    if has_primary_doc and not description and not synopsis:
        reason = "No description or synopsis found in primary doc"
        if reason not in seen_reasons:
            suspicious_reasons.append(reason)
            seen_reasons.add(reason)

    return {
        "has_primary_doc": has_primary_doc,
        "file_count": file_count,
        "size_bytes": size_bytes,
        "name": name,
        "description": description,
        "synopsis": synopsis,
        "suspicious_reasons": suspicious_reasons,
    }


__all__ = ["build_unit_metadata"]
