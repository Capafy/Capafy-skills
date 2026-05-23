from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class PackageContext:
    staging_root: Path
    package_json: str
    output_path: Path
    cleanup_staging: bool = False


@dataclass(frozen=True)
class ValidateContext:
    runtime_root: Path
    reviewed_scan_json: Optional[str] = None
    reviewed_scan_file: Optional[str] = None
    target: Any = None
    expected_version: Optional[str] = None
    resolved_target_name: str = ""


@dataclass(frozen=True)
class ArtifactPackageContext:
    effective_scan_payload: Dict[str, Any]


@dataclass(frozen=True)
class ArtifactValidateContext:
    effective_scan_payload: Dict[str, Any]
