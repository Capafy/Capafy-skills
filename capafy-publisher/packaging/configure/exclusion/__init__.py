from __future__ import annotations

from packaging._shared.common.exclusion_rules import (
    EXCLUDE_FILE_SUFFIXES,
    SOURCE_CODE_SUFFIXES,
    SPECIAL_SCAN_PATH_SUFFIXES,
    default_exclude_use,
    exclude_reason_code_for_path,
    looks_like_high_risk_file,
)

from .projection import build_exclude_entry, project_scan_excludes
from .stage import scan_only_excluded_credential_relpath, should_skip_high_risk_stage_file

__all__ = [
    "EXCLUDE_FILE_SUFFIXES",
    "SOURCE_CODE_SUFFIXES",
    "SPECIAL_SCAN_PATH_SUFFIXES",
    "build_exclude_entry",
    "default_exclude_use",
    "exclude_reason_code_for_path",
    "looks_like_high_risk_file",
    "project_scan_excludes",
    "scan_only_excluded_credential_relpath",
    "should_skip_high_risk_stage_file",
]
