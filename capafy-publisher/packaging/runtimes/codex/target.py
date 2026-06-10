from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Optional

from packaging._shared.codex.local_files import resolve_codex_local_config_file_source
from packaging._shared.common.fs import read_text
from packaging._shared.config_files.toml_loader import safe_toml_loads, tomllib
from packaging._shared.contracts.selectable import is_instruction_doc, should_skip_skill_reference_document
from packaging._shared.contracts.stage_plan import StagePlan
from packaging._shared.selection.local_ref_confirmation import display_path_for_local_reference
from packaging.runtimes.profile_target import EnvProfileTarget


class CodexTarget(EnvProfileTarget):
    _DEFAULT_ENV_ID = "codex"

    def finalize_cloud_hosted_packaging(self, staging_root: Path, stage_plan: StagePlan) -> dict:
        return _finalize_codex_cloud_hosted(staging_root, stage_plan)

    def collect_special_scan_candidates(
        self,
        path: Path,
        text: str,
        annotate_candidate,
    ) -> tuple[dict[str, str], dict[str, str], dict[str, str], list[dict]]:
        if path.name != "config.toml":
            return {}, {}, {}, []
        codex_scan_hints = import_module("packaging.configure.runtimes.codex.scan_hints")
        logical_env_source_path = import_module(
            "packaging.configure.scan.env_scan_rules"
        ).logical_env_source_path
        display_path = path.name
        source_display_path = logical_env_source_path(path, display_path)
        env_hints, val_hints, candidates = codex_scan_hints.collect_codex_toml_config_hints(
            text,
            display_path,
            source_display_path,
            annotate_candidate,
        )
        return env_hints, {}, val_hints, candidates

    def should_scan_structured_values(self, relpath: str) -> bool:
        codex_scan_hints = import_module("packaging.configure.runtimes.codex.scan_hints")
        return codex_scan_hints.should_scan_codex_structured_values(relpath)

    def iter_config_referenced_instruction_documents(self, stage_plan: StagePlan) -> list[dict]:
        config_path = _source_file_for_display_path(stage_plan, ".codex/config.toml")
        if config_path is None:
            return []
        text, _encoding = read_text(config_path)
        if text is None:
            return []
        try:
            payload = safe_toml_loads(text)
        except tomllib.TOMLDecodeError:
            return []
        raw_value = payload.get("model_instructions_file")
        if not isinstance(raw_value, str):
            return []
        return _config_referenced_instruction_document(
            resolve_codex_local_config_file_source(raw_value),
            stage_plan=stage_plan,
        )


def _ensure_codex_dotenv(staging_root: Path) -> bool:
    dotenv_path = staging_root / ".codex" / ".env"
    if dotenv_path.is_file():
        return False
    dotenv_path.parent.mkdir(parents=True, exist_ok=True)
    dotenv_path.write_text("", encoding="utf-8")
    return True


def _finalize_codex_cloud_hosted(staging_root: Path, stage_plan: StagePlan) -> dict:
    summary: dict = {
        "codex_model_instruction_files": 0,
    }
    summary["codex_dotenv_materialized"] = int(_ensure_codex_dotenv(staging_root))
    warnings: list[dict] = []
    config_path = staging_root / ".codex" / "config.toml"
    if config_path.is_file():
        stage_codex_model_instructions_file = import_module(
            "packaging.configure.runtimes.codex.model_instruction_staging"
        ).stage_codex_model_instructions_file
        summary["codex_model_instruction_files"] = stage_codex_model_instructions_file(
            config_path,
            staging_root,
            stage_plan=stage_plan,
            warnings=warnings,
        )
    if warnings:
        summary["codex_model_instruction_warnings"] = warnings
    return summary


def _source_file_for_display_path(stage_plan: StagePlan, display_path: str) -> Optional[Path]:
    normalized_display_path = display_path.strip().strip("/")
    if not normalized_display_path:
        return None
    for file_source in stage_plan.file_sources:
        if file_source.relative_target_path.as_posix() != normalized_display_path:
            continue
        source_file = file_source.source_file.expanduser()
        if source_file.is_file():
            return source_file
    return None


def _config_referenced_instruction_document(
    source_path: Optional[Path],
    *,
    stage_plan: StagePlan,
) -> list[dict]:
    if source_path is None or not source_path.is_file():
        return []
    display_path = display_path_for_local_reference(source_path, stage_plan)
    if not display_path or not is_instruction_doc(display_path):
        return []
    if should_skip_skill_reference_document(display_path):
        return []
    text, _encoding = read_text(source_path)
    if text is None or not text.strip():
        return []
    return [
        {
            "path": display_path,
            "text": text,
            "is_instruction": is_instruction_doc(display_path),
            "source_file": str(source_path),
        }
    ]


__all__ = [
    "CodexTarget",
]
