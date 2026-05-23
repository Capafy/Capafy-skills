from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Set

from packaging.configure.contracts import DeepScanFindingsInput
from packaging._shared.contracts.stage_plan import StagePlan


@dataclass(frozen=True)
class StageContext:
    staging_root: Path
    stage_plan: StagePlan
    bundle_context: Dict[str, Any]
    selected_skill_paths: Optional[Set[str]]
    target: Any
    workspace_documents_manifest_payload: Optional[Dict[str, Any]] = None
    selected_plugin_paths: Optional[Set[str]] = None
    selected_cron_paths: Optional[Set[str]] = None
    workspace_allowlist: Optional[Set[str]] = None


@dataclass(frozen=True)
class ConfigureContext:
    agent_id: str
    latest: Dict[str, Any]
    latest_state: Any
    manifest: Any
    deep_scan: bool = False
    overrides: Optional[Dict[str, str]] = None
    deep_scan_findings: DeepScanFindingsInput = DeepScanFindingsInput()
