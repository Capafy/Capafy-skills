from __future__ import annotations

import json
import os
import shlex
from pathlib import Path

from packaging._shared.common.constants import DEPENDENCY_MANIFEST_FILES
from packaging._shared.common.fs import relpath


def _shell_cd_prefix(project_path: str) -> str:
    if project_path in ("", "."):
        return ""
    return f"cd {shlex.quote(project_path)} && "


def build_install_commands(project_path: str, manifest_files: set[str]) -> list[str]:
    commands: list[str] = []
    prefix = _shell_cd_prefix(project_path)

    if "uv.lock" in manifest_files:
        commands.append(f"{prefix}uv sync --frozen")
    elif "poetry.lock" in manifest_files:
        commands.append(f"{prefix}poetry install --no-root")
    elif "Pipfile.lock" in manifest_files:
        commands.append(f"{prefix}pipenv sync")
    elif "Pipfile" in manifest_files:
        commands.append(f"{prefix}pipenv install")
    elif "requirements.txt" in manifest_files:
        commands.append(f"{prefix}pip install -r requirements.txt")
    elif "pyproject.toml" in manifest_files:
        commands.append(f"{prefix}pip install .")

    if "environment.yml" in manifest_files or "environment.yaml" in manifest_files:
        env_file = "environment.yml" if "environment.yml" in manifest_files else "environment.yaml"
        commands.append(f"{prefix}conda env update --file {env_file} --prune")

    if "pnpm-lock.yaml" in manifest_files:
        commands.append(f"{prefix}pnpm install --frozen-lockfile")
    elif "yarn.lock" in manifest_files:
        commands.append(f"{prefix}yarn install --frozen-lockfile")
    elif "package-lock.json" in manifest_files:
        commands.append(f"{prefix}npm ci")
    elif "package.json" in manifest_files:
        commands.append(f"{prefix}npm install")

    return commands


def write_runtime_dependencies_manifest(staging_root: Path) -> Path:
    manifest_projects: dict[str, set[str]] = {}
    for current, _, filenames in os.walk(staging_root, topdown=True):
        current_path = Path(current)
        rel_dir = relpath(current_path, staging_root)
        for filename in sorted(filenames):
            if filename not in DEPENDENCY_MANIFEST_FILES:
                continue
            project_path = "." if rel_dir == "." else rel_dir
            manifest_projects.setdefault(project_path, set()).add(filename)

    project_by_path: dict[str, dict] = {}
    for project_path in sorted(manifest_projects):
        manifest_files = manifest_projects[project_path]
        project_by_path[project_path] = {
            "path": project_path,
            "manifest_files": sorted(manifest_files),
            "commands": build_install_commands(project_path, manifest_files),
        }

    payload = []
    for project_path in sorted(project_by_path):
        entry = project_by_path[project_path]
        for command in entry["commands"]:
            payload.append(
                {
                    "path": entry["path"],
                    "manifest_files": entry["manifest_files"],
                    "command": command,
                }
            )
    output_path = staging_root / "agent.runtime_dependencies.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


__all__ = [
    "build_install_commands",
    "write_runtime_dependencies_manifest",
]
