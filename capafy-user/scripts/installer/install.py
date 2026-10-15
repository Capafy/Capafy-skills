from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile
from typing import Optional

from .archive import (
    discover_package_layout,
    extract_archive,
    resolve_install_target,
)


@dataclass(frozen=True)
class InstallItem:
    source: Path
    target: Path
    is_skill: bool


@dataclass(frozen=True)
class InstalledPackage:
    skill_dirs: tuple[Path, ...]
    shared_paths: tuple[Path, ...] = ()


class InstallRecoveryError(RuntimeError):
    """Recovery is incomplete; preserve the working directory in the error."""


def detect_install_root(script_path: Optional[Path] = None) -> Path:
    current = Path(script_path) if script_path is not None else Path(__file__).resolve()
    for parent in current.parents:
        if parent.name == "skills":
            return parent
    raise RuntimeError(
        "unable to determine install root from current user skill location; pass --install-root"
    )


def plan_installation(
    package_root: Path,
    skill_roots: tuple[Path, ...],
    install_root: Path,
    *,
    archive_path: Path,
    package_type: str,
    preferred_dir_name: Optional[str] = None,
    fallback_dir_names: tuple[Optional[str], ...] = (),
) -> tuple[InstallItem, ...]:
    # Validate package type and map all targets before writing; the Thin state contract always requires a single entry point.
    if package_type not in {"download", "thin_skill"}:
        raise RuntimeError(f"unsupported package type: {package_type}")
    if package_type == "thin_skill" and len(skill_roots) != 1:
        raise RuntimeError(
            "Thin Skill requires a single skill root; multiple roots are not supported by its state contract"
        )
    if skill_roots == (package_root,):
        target = resolve_install_target(
            package_root,
            install_root,
            archive_path=archive_path,
            preferred_dir_name=preferred_dir_name,
            fallback_dir_names=fallback_dir_names,
        )
        return (InstallItem(package_root, target, True),)

    items = tuple(
        InstallItem(source, install_root / source.name, source in skill_roots)
        for source in sorted(package_root.iterdir())
    )
    names = [item.target.name.casefold() for item in items]
    if len(names) != len(set(names)):
        raise RuntimeError("package contains case-insensitive install target collisions")
    return items


def _rollback_installation(items: tuple[InstallItem, ...], work: Path) -> list[str]:
    # Roll back from filesystem evidence: a backup means the old target moved, and missing staging means the new target was published.
    # Prepare every copy before the transaction so interruption immediately after rename needs no in-memory registration.
    errors = []
    for item in reversed(items):
        target = item.target
        prepared = work / "prepared" / target.name
        backup = work / "backup" / target.name
        try:
            if not prepared.exists() and (target.exists() or target.is_symlink()):
                if target.is_dir() and not target.is_symlink():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            if backup.exists():
                backup.rename(target)
        except OSError as exc:
            errors.append(f"{target}: {exc}")
    return errors


def _replace_install_targets(
    items: tuple[InstallItem, ...], work: Path, *, overwrite: bool
) -> None:
    # Preflight and copy the entire batch before moving old targets; a single Skill is a one-item transaction batch.
    for item in items:
        target = item.target
        if target.exists() or target.is_symlink():
            if not overwrite:
                raise FileExistsError(
                    f"target already exists: {target}; confirm replacement, then use --overwrite"
                )
            if target.is_symlink() or target.is_dir() != item.source.is_dir():
                raise RuntimeError(
                    f"refusing to overwrite non-directory or symlink/type mismatch: {target}"
                )

    prepared_root = work / "prepared"
    backup_root = work / "backup"
    prepared_root.mkdir()
    backup_root.mkdir()
    for item in items:
        prepared = prepared_root / item.target.name
        if item.source.is_dir():
            shutil.copytree(item.source, prepared)
        else:
            shutil.copy2(item.source, prepared)

    try:
        for item in items:
            if item.target.exists():
                item.target.rename(backup_root / item.target.name)
        for item in items:
            (prepared_root / item.target.name).rename(item.target)
    except BaseException as install_error:
        try:
            errors = _rollback_installation(items, work)
        except BaseException as rollback_error:
            errors = [str(rollback_error) or type(rollback_error).__name__]
        if errors:
            raise InstallRecoveryError(
                f"installation failed: {install_error}; rollback failed; "
                f"recovery files preserved at {work}: " + "; ".join(errors)
            ) from None
        raise


def install_from_file(
    archive_path: Path,
    destination_root: Optional[Path] = None,
    *,
    preferred_dir_name: Optional[str] = None,
    fallback_dir_names: tuple[Optional[str], ...] = (),
    overwrite: bool = False,
    package_type: str = "download",
) -> InstalledPackage:
    # Stage under the installation root to keep publication renames on one filesystem; all layouts share a fixed return type.
    install_root = destination_root or detect_install_root()
    install_root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=".capafy-install-", dir=install_root))
    try:
        extracted = extract_archive(archive_path, work / "extract")
        package_root, skill_roots = discover_package_layout(extracted)
        items = plan_installation(
            package_root,
            skill_roots,
            install_root,
            archive_path=archive_path,
            package_type=package_type,
            preferred_dir_name=preferred_dir_name,
            fallback_dir_names=fallback_dir_names,
        )
        _replace_install_targets(items, work, overwrite=overwrite)
        installed = InstalledPackage(
            skill_dirs=tuple(item.target for item in items if item.is_skill),
            shared_paths=tuple(item.target for item in items if not item.is_skill),
        )
    except InstallRecoveryError:
        # Retain the whole working directory after incomplete recovery to avoid deleting the only old copy.
        raise
    except BaseException as exc:
        # Handle interruption at the transaction return boundary; remaining backups require an explicit error with recovery paths.
        backup_root = work / "backup"
        if backup_root.exists() and any(backup_root.iterdir()):
            raise InstallRecoveryError(
                f"installation failed: {exc}; recovery files preserved at {work}"
            ) from exc
        shutil.rmtree(work, ignore_errors=True)
        raise
    else:
        shutil.rmtree(work, ignore_errors=True)
        return installed
