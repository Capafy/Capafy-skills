from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
from typing import Optional

from .archive import resolve_install_target, validate_package_layout
from .install import InstalledPackage


ENV_PATTERNS = (
    re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}"),
    re.compile(r"process\.env\.([A-Z][A-Z0-9_]*)"),
    re.compile(r"os\.environ\[\s*['\"]([A-Z][A-Z0-9_]*)['\"]\s*\]"),
    re.compile(r"os\.getenv\(\s*['\"]([A-Z][A-Z0-9_]*)['\"]\s*\)"),
)


def collect_env_vars_needed(package_root: Path) -> list[str]:
    # Shared content may be a directory or a file; callers specify the audit boundary instead of scanning the entire host installation root.
    names: set[str] = set()
    paths = (package_root,) if package_root.is_file() else package_root.rglob("*")
    for path in paths:
        if not path.is_file():
            continue
        if path.suffix in {".pyc", ".gz", ".zip", ".png", ".jpg", ".jpeg", ".pdf"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in ENV_PATTERNS:
            names.update(pattern.findall(text))
    return sorted(names)


def _default_runner(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True)


def install_dependencies(
    package_root: Path,
    runner=None,
    *,
    execute_installers: bool = True,
) -> dict[str, object]:
    # Inspect only direct manifests in directories and root shared manifests themselves; never recursively execute unknown installation scripts.
    dependency_root = package_root if package_root.is_dir() else package_root.parent
    manifests = (
        package_root / "requirements.txt",
        package_root / "package.json",
    ) if package_root.is_dir() else (package_root,)
    commands: list[tuple[list[str], Path]] = []

    for manifest in manifests:
        if not manifest.is_file():
            continue
        if manifest.name == "requirements.txt":
            commands.append((
                ["python3", "-m", "pip", "install", "-r", str(manifest.resolve())],
                dependency_root,
            ))
        elif manifest.name == "package.json":
            commands.append((["npm", "install"], dependency_root))

    execute = runner or _default_runner
    deps_ok = True
    missing_deps: set[str] = set()
    if not execute_installers:
        for cmd, _cwd in commands:
            if shutil.which(cmd[0]) is None:
                deps_ok = False
                missing_deps.add(cmd[0])
        return {"deps_ok": deps_ok, "missing_deps": sorted(missing_deps)}

    for cmd, cwd in commands:
        try:
            execute(cmd, cwd)
        except FileNotFoundError:
            deps_ok = False
            missing_deps.add(cmd[0])
        except subprocess.CalledProcessError:
            deps_ok = False
            missing_deps.add(cmd[0])
    return {"deps_ok": deps_ok, "missing_deps": sorted(missing_deps)}


def _inspect_install_content(
    package_root: Path,
    runner=None,
    *,
    execute_installers: bool = True,
) -> dict[str, object]:
    install_report = install_dependencies(
        package_root,
        runner=runner,
        execute_installers=execute_installers,
    )
    install_report["env_vars_needed"] = collect_env_vars_needed(package_root)
    return install_report


def inspect_install_target(
    package_root: Path,
    runner=None,
    *,
    execute_installers: bool = True,
    install_root: Optional[Path] = None,
    archive_path: Optional[Path] = None,
) -> dict[str, object]:
    validate_package_layout(package_root)
    install_report = _inspect_install_content(
        package_root,
        runner=runner,
        execute_installers=execute_installers,
    )
    if install_root is not None:
        install_report["install_target"] = str(
            resolve_install_target(package_root, install_root, archive_path=archive_path)
        )
    return install_report


def build_install_report(
    installed: InstalledPackage,
    *,
    execute_installers: bool = True,
    runner=None,
) -> dict[str, object]:
    # Inspect shared content before Skills; preserve individual results and aggregate them visibly at the top level.
    def inspect_paths(paths, inspect):
        return [
            dict(
                inspect(
                    target,
                    runner=runner,
                    execute_installers=execute_installers,
                ),
                installed_to=str(target),
            )
            for target in paths
        ]

    shared_details = inspect_paths(installed.shared_paths, _inspect_install_content)
    skill_details = inspect_paths(installed.skill_dirs, inspect_install_target)
    all_details = shared_details + skill_details
    skill_paths = [str(target) for target in installed.skill_dirs]
    return {
        "installed_to": skill_paths[0] if len(skill_paths) == 1 else skill_paths,
        "installed_skills": skill_details,
        "shared_paths": [str(path) for path in installed.shared_paths],
        "installed_shared": shared_details,
        "deps_ok": all(detail["deps_ok"] for detail in all_details),
        "missing_deps": sorted({
            name for detail in all_details for name in detail["missing_deps"]
        }),
        "env_vars_needed": sorted({
            name for detail in all_details for name in detail["env_vars_needed"]
        }),
    }
