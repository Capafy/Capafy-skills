from __future__ import annotations

from pathlib import Path, PurePosixPath
import re
import tarfile
from typing import Optional
import zipfile


SKILL_NAME_PATTERN = re.compile(r"(?m)^name:\s*(.+?)\s*$")


def _detect_archive_format(archive_path: Path) -> str:
    with archive_path.open("rb") as fp:
        head = fp.read(4)
    if head[:2] == b"PK":
        return "zip"
    if head[:2] == b"\x1f\x8b":
        return "tar.gz"
    raise RuntimeError(f"unsupported archive format: {archive_path}")


def _validate_archive_member(name: str, *, is_link: bool = False) -> None:
    # Reject links, parent traversal, and Windows absolute paths before extraction so no member escapes staging.
    path = PurePosixPath(name.replace("\\", "/"))
    if is_link or path.is_absolute() or ".." in path.parts or re.match(r"^[A-Za-z]:", name):
        raise RuntimeError(f"unsafe archive member (path traversal or link): {name}")


def _sibling_skill_roots(container: Path) -> list[Path]:
    # Only direct container children can be sibling Skills; components nested inside a Skill remain part of it.
    roots = sorted(
        child for child in container.iterdir()
        if child.is_dir() and (child / "SKILL.md").is_file()
    )
    if len(roots) < 2:
        return []
    if any(
        not any(root in entry.parents for root in roots)
        for entry in container.rglob("SKILL.md")
        if entry.is_file()
    ):
        return []
    return roots


def extract_archive(archive_path: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    fmt = _detect_archive_format(archive_path)
    if fmt == "zip":
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                _validate_archive_member(
                    member.filename,
                    is_link=(member.external_attr >> 16) & 0o170000 == 0o120000,
                )
            archive.extractall(destination)
    else:
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in archive.getmembers():
                _validate_archive_member(
                    member.name,
                    is_link=not (member.isfile() or member.isdir()),
                )
            try:
                archive.extractall(destination, filter="data")
            except TypeError:
                archive.extractall(destination)
    return destination


def discover_package_layout(extracted: Path) -> tuple[Path, tuple[Path, ...]]:
    # Unwrap only directories with no sibling content; retain explicit sibling Skills and their shared container content.
    package_root = extracted
    while not (package_root / "SKILL.md").is_file():
        children = list(package_root.iterdir())
        if len(children) == 1 and children[0].is_dir():
            package_root = children[0]
            continue
        skill_roots = _sibling_skill_roots(package_root)
        if skill_roots:
            return package_root, tuple(skill_roots)
        nested_entries = sorted(
            str(path.relative_to(extracted))
            for path in package_root.rglob("SKILL.md")
            if path.is_file()
        )
        if nested_entries:
            raise RuntimeError(
                "unsupported package layout: cannot select a single skill root without "
                "discarding sibling content; entries: " + ", ".join(nested_entries)
            )
        break
    validate_package_layout(package_root)
    return package_root, (package_root,)


def _try_normalize_skill_dir_name(raw_name: Optional[str]) -> Optional[str]:
    normalized = re.sub(
        r"[^A-Za-z0-9._-]+", "-", str(raw_name or "").strip()
    ).strip(".-")
    return normalized or None


def _read_skill_name(package_root: Path) -> Optional[str]:
    skill_md = package_root / "SKILL.md"
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return None

    # Read names only from YAML frontmatter; support BOM and CRLF without treating body text as directory names.
    text = text.lstrip("\ufeff").replace("\r\n", "\n")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            match = SKILL_NAME_PATTERN.search(text[3:end])
            if match:
                return _try_normalize_skill_dir_name(match.group(1))
    return None


def _read_archive_top_levels(archive_path: Path) -> list[str]:
    fmt = _detect_archive_format(archive_path)
    if fmt == "zip":
        with zipfile.ZipFile(archive_path) as archive:
            top_levels = {
                name.split("/")[0]
                for name in archive.namelist()
                if name and name not in {".", "./"}
            }
    else:
        with tarfile.open(archive_path, "r:gz") as archive:
            top_levels = {
                member.name.split("/")[0]
                for member in archive.getmembers()
                if member.name and member.name not in {".", "./"}
            }
    return sorted(top_levels)


def resolve_install_dir_name(
    package_root: Path,
    *,
    archive_path: Optional[Path] = None,
    preferred_dir_name: Optional[str] = None,
    fallback_dir_names: tuple[Optional[str], ...] = (),
) -> str:
    validate_package_layout(package_root)

    preferred_name = _try_normalize_skill_dir_name(preferred_dir_name)
    if preferred_name:
        return preferred_name

    skill_name = _read_skill_name(package_root)
    if skill_name:
        return skill_name

    if archive_path is not None:
        top_levels = _read_archive_top_levels(archive_path)
        if len(top_levels) == 1 and top_levels[0] != "SKILL.md":
            package_dir_name = _try_normalize_skill_dir_name(package_root.name)
            if package_dir_name:
                return package_dir_name

    for fallback_dir_name in fallback_dir_names:
        normalized = _try_normalize_skill_dir_name(fallback_dir_name)
        if normalized:
            return normalized

    if archive_path is None:
        package_dir_name = _try_normalize_skill_dir_name(package_root.name)
        if package_dir_name:
            return package_dir_name

    raise RuntimeError(
        "unable to determine safe install directory name from package; "
        "use an ASCII name or provide folder, Agent, or template metadata"
    )


def resolve_install_target(
    package_root: Path,
    install_root: Path,
    *,
    archive_path: Optional[Path] = None,
    preferred_dir_name: Optional[str] = None,
    fallback_dir_names: tuple[Optional[str], ...] = (),
) -> Path:
    install_dir_name = resolve_install_dir_name(
        package_root,
        archive_path=archive_path,
        preferred_dir_name=preferred_dir_name,
        fallback_dir_names=fallback_dir_names,
    )
    target = install_root / install_dir_name
    if target == install_root:
        raise RuntimeError("refusing to install package directly into skills root")
    return target


def validate_package_layout(package_root: Path) -> None:
    if not package_root.exists() or not package_root.is_dir():
        raise RuntimeError(f"invalid package directory: {package_root}")
    if not (package_root / "SKILL.md").is_file():
        raise RuntimeError(f"invalid package layout: missing SKILL.md in {package_root}")
