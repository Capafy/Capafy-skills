from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath

from packaging._shared.common.toml_loader import safe_toml_loads, tomllib


ENV_ASSIGNMENT_PATTERN = re.compile(r"^\s*(?:export\s+)?[A-Za-z_][A-Za-z0-9_]*\s*=")


def collect_present_runtime_paths(profile: dict, runtime_root: Path) -> list[str]:
    present: list[str] = []

    for group_name in ("skill_roots", "fixed_stage_files", "redact_files"):
        for spec in profile.get(group_name, []):
            if not isinstance(spec, dict):
                continue
            target_path = str(spec.get("target_path", "")).strip()
            if not target_path:
                continue
            source_value = str(spec.get("source_value", "")).strip()


            if group_name == "fixed_stage_files" and source_value and source_value != "copied":
                continue
            if (runtime_root / target_path).exists() and target_path not in present:
                present.append(target_path)

    agents_skills_root = runtime_root / ".agents" / "skills"
    if agents_skills_root.exists() and ".agents/skills" not in present:
        present.append(".agents/skills")
    return present


def collect_required_runtime_paths(profile: dict) -> list[str]:
    required: list[str] = []
    for spec in profile.get("fixed_stage_files", []):
        if not isinstance(spec, dict):
            continue
        target_path = str(spec.get("target_path", "")).strip()
        if not target_path:
            continue
        source_value = str(spec.get("source_value", "")).strip()


        if source_value and source_value != "copied":
            continue
        if target_path not in required:
            required.append(target_path)
    return required


def _infer_validation_kind(path: str, strategy: str) -> str:
    if strategy in {"json_local_config", "json_stage_config"}:
        return "json"
    if strategy in {"toml_local_config", "toml_stage_config"}:
        return "toml"
    if strategy == "env_file":
        return "env"
    if strategy == "markdown_instruction":
        return "text"

    pure = PurePosixPath(path)
    lowered = pure.name.lower()
    if pure.suffix.lower() == ".json":
        return "json"
    if pure.suffix.lower() == ".toml":
        return "toml"
    if lowered == ".env" or lowered.endswith(".env"):
        return "env"
    if pure.suffix.lower() in {".md", ".markdown", ".mdx", ".txt"}:
        return "text"
    return "text"


def collect_validation_targets(profile: dict, runtime_root: Path) -> list[dict[str, str]]:
    targets: dict[str, dict[str, str]] = {}

    for spec in profile.get("fixed_stage_files", []):
        if not isinstance(spec, dict):
            continue
        target_path = str(spec.get("target_path", "")).strip()
        if not target_path:
            continue
        if not (runtime_root / target_path).is_file():
            continue
        targets.setdefault(
            target_path,
            {
                "path": target_path,
                "strategy": "",
            },
        )

    for spec in profile.get("redact_files", []):
        if not isinstance(spec, dict):
            continue
        target_path = str(spec.get("target_path", "")).strip()
        if not target_path:
            continue
        if not (runtime_root / target_path).is_file():
            continue
        targets[target_path] = {
            "path": target_path,
            "strategy": str(spec.get("strategy", "")).strip(),
        }

    return [targets[path] for path in sorted(targets)]


def _validate_env_text(text: str) -> list[str]:
    errors: list[str] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if not ENV_ASSIGNMENT_PATTERN.match(line):
            errors.append(f"line {line_no} is not a valid env assignment")
    return errors


def validate_target_file(runtime_root: Path, target: dict[str, str]) -> tuple[bool, str]:
    path = runtime_root / target["path"]
    kind = _infer_validation_kind(target["path"], target.get("strategy", ""))
    text = path.read_text(encoding="utf-8")

    if kind == "json":
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"failed to parse JSON at {target['path']}: {exc}") from exc
        return True, f"{target['path']} JSON parsed successfully"
    if kind == "toml":
        try:
            safe_toml_loads(text)
        except tomllib.TOMLDecodeError as exc:
            raise ValueError(f"failed to parse TOML at {target['path']}: {exc}") from exc
        return True, f"{target['path']} TOML parsed successfully"
    if kind == "env":
        env_errors = _validate_env_text(text)
        if env_errors:
            raise ValueError(f"env validation failed for {target['path']}: {env_errors[0]}")
        return True, f"{target['path']} env validation passed"
    if not text.strip():
        raise ValueError(f"{target['path']} is empty")
    return True, f"{target['path']} text is readable"
