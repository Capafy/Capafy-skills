#!/usr/bin/env python3
"""User Skill self-updater.

Per-file overwrite strategy (cross-platform safe). Designed to update the skill
even when the skill directory is held open by the parent Claude Code process
on Windows: instead of renaming the directory, individual files are replaced
in place via os.replace; locked files fall back to ``<file>.new`` staging and
are promoted on the next ``--finalize`` run.

Usage:
    python3 scripts/self_update.py --check
    python3 scripts/self_update.py
    python3 scripts/self_update.py --finalize
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shlex
import subprocess
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

try:
    from . import runtime_context
    from .defaults import DEFAULT_PLATFORM_BASE_URL
except ImportError:  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import runtime_context  # type: ignore
    from defaults import DEFAULT_PLATFORM_BASE_URL  # type: ignore


VERSION_MANIFEST_PATH = "/public/client-agent-version/user"
PLATFORM_BASE_URL_ENV = "CAPAFY_PLATFORM_BASE_URL"
STATE_RELATIVE_PATH = Path(".temp") / "self-update-state.json"
PENDING_RELATIVE_PATH = Path(".temp") / "self-update-pending.json"
LOCK_RELATIVE_PATH = Path(".temp") / "self-update.lock"
SELF_UPDATE_PIP_ARGS_ENV = "CAPAFY_SELF_UPDATE_PIP_ARGS"
SELF_UPDATE_SKILL_DIR_ENV = "CAPAFY_SELF_UPDATE_SKILL_DIR"
STAGING_DIR_SUFFIX = ".staging"
SNAPSHOT_DIR_SUFFIX = ".snapshot"
PENDING_SUFFIX = ".new"

# Top-level paths inside the skill that the updater must NEVER touch.
# Matched against rel_path.parts[0]: protects the entire subtree if a directory.
PROTECTED_TOP_LEVEL = frozenset({
    ".temp",
    ".cache",
    "config.json",
    "thin_skills_state.json",
    "skills",
})


# --------------------------------------------------------------------------- #
# Generic helpers
# --------------------------------------------------------------------------- #

def _unlink_if_exists(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except IsADirectoryError:
        shutil.rmtree(path, ignore_errors=True)


def _safe_chmod(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def _is_protected(rel_path: Path) -> bool:
    """True when this relative path must never be overwritten or swept."""
    parts = rel_path.parts
    if not parts:
        return True
    return parts[0] in PROTECTED_TOP_LEVEL


def _version_tuple(version_str: str) -> tuple[int, ...]:
    """Parse '1.2.1' into (1, 2, 1) for comparison."""
    parts: list[int] = []
    for segment in version_str.lstrip("vV").split("."):
        numeric = segment.split("-")[0]
        try:
            parts.append(int(numeric))
        except ValueError:
            break
    return tuple(parts)


def _detect_skill_dir() -> Path:
    """Resolve the skill directory (parent of scripts/, where this script lives)."""
    override = str(os.environ.get(SELF_UPDATE_SKILL_DIR_ENV, "")).strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


def _state_path(skill_dir: Path) -> Path:
    return skill_dir / STATE_RELATIVE_PATH


def _pending_path(skill_dir: Path) -> Path:
    return skill_dir / PENDING_RELATIVE_PATH


def _lock_path(skill_dir: Path) -> Path:
    return skill_dir / LOCK_RELATIVE_PATH


@contextlib.contextmanager
def _exclusive_lock(skill_dir: Path):
    """Best-effort cross-platform file lock around an update run.

    Raises RuntimeError if another self_update.py is already holding the lock.
    Released automatically on context exit, including on exceptions.
    """
    lock_path = _lock_path(skill_dir)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    # Open in append+read so the file gets created if missing without
    # truncating an existing lock holder's handle.
    fp = open(lock_path, "a+")
    acquired = False
    try:
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(fp.fileno(), msvcrt.LK_NBLCK, 1)
                acquired = True
            except OSError as exc:
                raise RuntimeError(
                    "another self_update.py is already running for this skill "
                    "(lock held). Wait for it to finish, or remove the stale "
                    f"lock file at {lock_path} if no updater is running."
                ) from exc
        else:
            import fcntl
            try:
                fcntl.flock(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError as exc:
                raise RuntimeError(
                    "another self_update.py is already running for this skill "
                    "(lock held). Wait for it to finish, or remove the stale "
                    f"lock file at {lock_path} if no updater is running."
                ) from exc
        yield
    finally:
        if acquired:
            try:
                if os.name == "nt":
                    import msvcrt
                    try:
                        # Rewind before unlocking the same byte range.
                        fp.seek(0)
                        msvcrt.locking(fp.fileno(), msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass
                else:
                    import fcntl
                    try:
                        fcntl.flock(fp, fcntl.LOCK_UN)
                    except OSError:
                        pass
            finally:
                fp.close()
        else:
            fp.close()


# --------------------------------------------------------------------------- #
def _normalize_platform_base_url(base_url: str | None) -> str:
    candidate = str(
        base_url
        or os.environ.get(PLATFORM_BASE_URL_ENV)
        or DEFAULT_PLATFORM_BASE_URL
    ).strip()
    if not candidate:
        raise ValueError("platform base_url must not be empty")
    if "://" not in candidate:
        raise ValueError("platform base_url must include http:// or https://")
    return candidate.rstrip("/")


def _load_installed_version_state(skill_dir: Path) -> dict | None:
    state_path = _state_path(skill_dir)
    if not state_path.is_file():
        return None
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def get_local_version(skill_dir: Path | None = None) -> str:
    """Read current installed version, preferring explicit self-update state."""
    root = skill_dir or _detect_skill_dir()
    state = _load_installed_version_state(root)
    if state is not None:
        version = str(state.get("version", "")).strip()
        if version:
            return version

    index_path = root / "api-docs" / "index.json"
    if not index_path.is_file():
        raise RuntimeError(f"cannot read local version: {index_path} not found")
    data = json.loads(index_path.read_text(encoding="utf-8"))
    version = str(data.get("version", "")).strip()
    if not version:
        raise RuntimeError("local version field missing in api-docs/index.json")
    return version


def _persist_installed_version_state(
    skill_dir: Path,
    *,
    version: str,
    manifest_url: str,
    download_url: str,
) -> None:
    state_path = _state_path(skill_dir)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "version": version,
                "manifest_url": manifest_url,
                "download_url": download_url,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


# --------------------------------------------------------------------------- #
# Pending-files IO (for files that were locked during commit)
# --------------------------------------------------------------------------- #

def _read_pending(skill_dir: Path) -> list[str]:
    pending_path = _pending_path(skill_dir)
    if not pending_path.is_file():
        return []
    try:
        payload = json.loads(pending_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    items = payload.get("pending", [])
    if not isinstance(items, list):
        return []
    return [str(x) for x in items if isinstance(x, str)]


def _write_pending(skill_dir: Path, pending: list[str]) -> None:
    pending_path = _pending_path(skill_dir)
    pending_path.parent.mkdir(parents=True, exist_ok=True)
    pending_path.write_text(
        json.dumps({"pending": sorted(set(pending))}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )


def _clear_pending(skill_dir: Path) -> None:
    _unlink_if_exists(_pending_path(skill_dir))


# --------------------------------------------------------------------------- #
# Manifest fetch
# --------------------------------------------------------------------------- #

def _read_url_bytes(url: str, *, timeout: int, include_platform_context: bool = False) -> bytes:
    headers = {"User-Agent": "capafy-user-skill-updater"}
    if include_platform_context:
        headers.update(runtime_context.platform_context_headers())
    req = urllib.request.Request(
        url,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"request failed: {exc.code} {exc.reason}") from exc
    except (OSError, urllib.error.URLError) as exc:
        raise RuntimeError(f"request failed: {exc}") from exc


def resolve_version_manifest_url(
    manifest_url: str | None = None,
    *,
    base_url: str | None = None,
) -> str:
    """Resolve the version endpoint against the current platform base URL."""
    endpoint = str(manifest_url or VERSION_MANIFEST_PATH).strip()
    if not endpoint:
        endpoint = VERSION_MANIFEST_PATH
    if "://" in endpoint:
        return endpoint
    if not endpoint.startswith("/"):
        endpoint = f"/{endpoint}"
    return f"{_normalize_platform_base_url(base_url)}{endpoint}"


def _normalize_sha256(value: object) -> str | None:
    if value is None:
        return None
    digest = str(value).strip().lower()
    if not digest:
        return None
    if digest.startswith("sha256:"):
        digest = digest.split(":", 1)[1].strip()
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise RuntimeError("invalid version manifest: sha256 must be a 64-character hex digest")
    return digest


def fetch_version_manifest(
    manifest_url: str | None = None,
    *,
    base_url: str | None = None,
) -> dict:
    """Load the install manifest and normalize key fields."""
    resolved_manifest_url = resolve_version_manifest_url(manifest_url, base_url=base_url)
    try:
        payload = json.loads(
            _read_url_bytes(
                resolved_manifest_url,
                timeout=30,
                include_platform_context=True,
            ).decode("utf-8")
        )
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid version manifest JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("invalid version manifest: expected JSON object")

    data_payload = payload.get("data")
    if isinstance(data_payload, dict):
        payload = data_payload

    version = str(payload.get("version", "")).strip()
    download_url = str(payload.get("downloadUrl") or "").strip()
    sha256 = _normalize_sha256(
        payload.get("sha256")
        or payload.get("sha256Hex")
        or payload.get("sha256_hex")
    )
    if not version or not download_url:
        raise RuntimeError("invalid version manifest: missing version or downloadUrl")

    return {
        "version": version,
        "download_url": download_url,
        "sha256": sha256,
        "name": str(payload.get("name", "")).strip(),
        "description": str(payload.get("description", "")).strip(),
        "manifest_url": resolved_manifest_url,
    }


# --------------------------------------------------------------------------- #
# Download + verify
# --------------------------------------------------------------------------- #

def _write_temp_file(data: bytes, *, suffix: str) -> Path:
    fd, path = tempfile.mkstemp(prefix="capafy-user-update-", suffix=suffix)
    temp_path = Path(path)
    with open(fd, "wb", closefd=True) as handle:
        handle.write(data)
    return temp_path


def download_release(download_url: str) -> Path:
    """Download the published skill zip to a temp file."""
    archive_path = _write_temp_file(
        _read_url_bytes(download_url, timeout=120),
        suffix=".zip",
    )
    if not zipfile.is_zipfile(archive_path):
        _unlink_if_exists(archive_path)
        raise RuntimeError("downloaded file is not a valid zip archive")
    return archive_path


def _verify_archive_digest(archive_path: Path, expected_sha256: str | None) -> None:
    if not expected_sha256:
        return
    digest = hashlib.sha256()
    with archive_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    actual_sha256 = digest.hexdigest()
    if actual_sha256 != expected_sha256:
        raise RuntimeError(
            "downloaded archive sha256 mismatch: "
            f"expected {expected_sha256}, got {actual_sha256}"
        )


# --------------------------------------------------------------------------- #
# Zip extract + flatten + verify (now operate on a staging dir, not root)
# --------------------------------------------------------------------------- #

def _safe_zip_extractall(archive_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive_path, "r") as archive:
        resolved_destination = destination.resolve()
        for member in archive.infolist():
            # Reject symlinks (Unix external_attr encodes file type in upper 16 bits)
            if (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise RuntimeError(f"archive contains symlink entry: {member.filename}")
            resolved_member = (destination / member.filename).resolve()
            if (
                resolved_member != resolved_destination
                and resolved_destination not in resolved_member.parents
            ):
                raise RuntimeError(f"archive member escapes target directory: {member.filename}")
        archive.extractall(destination)


def _flatten_extracted_root(root: Path) -> None:
    """If the zip has a single top-level directory wrapper, hoist its contents."""
    children = [path for path in root.iterdir()]
    if (
        len(children) == 1
        and children[0].is_dir()
        and not (root / "SKILL.md").is_file()
    ):
        inner = children[0]
        for item in inner.iterdir():
            shutil.move(str(item), str(root / item.name))
        inner.rmdir()
        return

    if (root / "SKILL.md").is_file():
        return

    skill_subdir = next(
        (p for p in (root / "capafy-user", root / "skill") if p.is_dir()),
        None,
    )
    if skill_subdir is None:
        return

    tmp_skill = Path(tempfile.mkdtemp(prefix=".skill_tmp_", dir=root))
    try:
        shutil.move(str(skill_subdir), str(tmp_skill / "inner"))
        inner = tmp_skill / "inner"
        for item in list(root.iterdir()):
            if item == tmp_skill:
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        for item in inner.iterdir():
            shutil.move(str(item), str(root / item.name))
    finally:
        shutil.rmtree(tmp_skill, ignore_errors=True)


def _verify_skill_layout(root: Path) -> str:
    """Ensure the directory looks like a valid skill payload; return version."""
    if not (root / "SKILL.md").is_file():
        raise RuntimeError("staged skill missing SKILL.md")
    if not (root / "scripts").is_dir():
        raise RuntimeError("staged skill missing scripts/ directory")
    index_path = root / "api-docs" / "index.json"
    if not index_path.is_file():
        raise RuntimeError("staged skill missing api-docs/index.json")
    try:
        version = str(json.loads(index_path.read_text(encoding="utf-8"))["version"]).strip()
    except (json.JSONDecodeError, KeyError, OSError) as exc:
        raise RuntimeError(f"staged skill has invalid api-docs/index.json: {exc}") from exc
    if not version:
        raise RuntimeError("staged skill has empty version in api-docs/index.json")
    return version


# --------------------------------------------------------------------------- #
# Per-file install: stage / snapshot / commit / sweep / restore
# --------------------------------------------------------------------------- #

def _remove_existing_path(path: Path, *, label: str) -> None:
    if not path.exists():
        return
    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    except OSError as exc:
        raise RuntimeError(f"cannot remove {label}: {path}: {exc}") from exc
    if path.exists():
        raise RuntimeError(f"cannot remove {label}: {path} still exists")


def _snapshot_current_files(root: Path, snapshot: Path) -> None:
    """Copy the current non-protected files into snapshot/ for rollback."""
    snapshot.mkdir(parents=True, exist_ok=True)
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if _is_protected(rel):
            continue
        # Skip our own staging markers if any are lying around
        if path.name.endswith(PENDING_SUFFIX):
            continue
        target = snapshot / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def _seed_protected_defaults(staging: Path, root: Path) -> list[str]:
    """For PROTECTED top-level paths (e.g. config.json), copy from staging
    only when root has no copy yet.

    This handles fresh installs: a user running the per-file installer for the
    first time would otherwise end up with no config.json at all because
    PROTECTED paths are excluded from the regular commit. On subsequent updates
    this is a no-op since the file already exists.

    Returns the list of POSIX-style relative paths that were actually seeded,
    so a subsequent rollback can erase them and restore the pre-update state
    exactly.
    """
    seeded: list[str] = []
    for path in staging.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(staging)
        if not _is_protected(rel):
            continue
        target = root / rel
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(path, target)
            seeded.append(rel.as_posix())
        except OSError:
            # Best-effort; not fatal — the user can populate config later.
            continue
    return seeded


def _erase_seeded(root: Path, seeded_rels: list[str]) -> None:
    """Reverse of _seed_protected_defaults: delete only the paths that this
    install actually created. Used during rollback to keep the post-rollback
    state byte-equivalent to the pre-update state.
    """
    for rel in seeded_rels:
        target = root / rel
        try:
            target.unlink()
        except (FileNotFoundError, OSError):
            continue


def _commit_files_into_root(staging: Path, root: Path) -> list[str]:
    """Walk staging/ and replace each file in root/ in place.

    Returns a list of relative POSIX paths that could not be replaced
    (file in use); those are written to ``<file>.new`` for next-run promotion.
    """
    pending: list[str] = []

    try:
        self_update_rel = Path(__file__).resolve().relative_to(_detect_skill_dir().resolve())
    except ValueError:
        self_update_rel = Path("scripts") / Path(__file__).resolve().name
    files: list[Path] = [p for p in staging.rglob("*") if p.is_file()]
    # Process the top-level self_update.py last so the rest of the update
    # logic finishes against the version of the script the user actually
    # launched. Match by relative path (not bare basename) so a same-named
    # file under a sub-folder like examples/ isn't reordered.
    files.sort(
        key=lambda p: (
            p.relative_to(staging) == Path(self_update_rel),
            p.as_posix(),
        )
    )

    for staged_file in files:
        rel = staged_file.relative_to(staging)
        if _is_protected(rel):
            continue
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if not _replace_file(staged_file, target):
            pending.append(rel.as_posix())

    return pending


def _replace_file(src: Path, dst: Path) -> bool:
    """Replace dst with src in place. Return True on success.

    On PermissionError (Windows file lock), copy src to ``dst.new`` and
    return False so the caller can record it as pending.
    """
    try:
        os.replace(src, dst)
        return True
    except PermissionError:
        return _stage_as_new(src, dst)
    except OSError:
        # Cross-volume or similar fallback: copy + replace
        try:
            tmp = dst.with_name(dst.name + ".tmp_replace")
            shutil.copy2(src, tmp)
            try:
                os.replace(tmp, dst)
                return True
            except PermissionError:
                _unlink_if_exists(tmp)
                return _stage_as_new(src, dst)
        except OSError:
            return _stage_as_new(src, dst)


def _stage_as_new(src: Path, dst: Path) -> bool:
    new_target = dst.with_name(dst.name + PENDING_SUFFIX)
    try:
        shutil.copy2(src, new_target)
    except OSError as exc:
        raise RuntimeError(f"cannot stage update for {dst}: {exc}") from exc
    return False


def _collect_relative_files(root: Path) -> set[str]:
    """Return the set of POSIX-style relative paths for every file under root."""
    return {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file()
    }


def _sweep_files_not_in(
    root: Path,
    expected_rels: set[str],
    *,
    sweep_pending_markers: bool = False,
) -> None:
    """Delete files in root/ whose relative path is not in expected_rels.

    Always skips PROTECTED top-level paths. Pending ``*.new`` markers are
    preserved by default (they belong to a still-in-progress update); during
    rollback callers pass ``sweep_pending_markers=True`` to wipe them too.
    Best-effort: locked files are tolerated.
    """
    for path in list(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if _is_protected(rel):
            continue
        if path.name.endswith(PENDING_SUFFIX):
            if not sweep_pending_markers:
                continue
            try:
                path.unlink()
            except OSError:
                pass
            continue
        if rel.as_posix() in expected_rels:
            continue
        try:
            path.unlink()
        except OSError:
            continue

    # Sweep now-empty directories (deepest-first).
    dirs = sorted(
        (p for p in root.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    )
    for d in dirs:
        rel = d.relative_to(root)
        if _is_protected(rel):
            continue
        try:
            if not any(d.iterdir()):
                d.rmdir()
        except OSError:
            continue


def _sweep_dead_pending_markers(root: Path, current_pending: list[str]) -> None:
    """Delete any ``*.new`` artefacts in root/ that don't correspond to the
    given pending list. Without this, a file that was locked in a previous
    update but committed cleanly in a later one would leave its old ``.new``
    sibling on disk forever — they accumulate one per failed lock.
    """
    keep = set(current_pending)
    for path in list(root.rglob("*")):
        if not path.is_file():
            continue
        if not path.name.endswith(PENDING_SUFFIX):
            continue
        rel = path.relative_to(root)
        if _is_protected(rel):
            continue
        # Strip the .new suffix to recover the base relative path.
        base_rel = rel.with_name(path.name[: -len(PENDING_SUFFIX)]).as_posix()
        if base_rel in keep:
            continue
        try:
            path.unlink()
        except OSError:
            continue


def _restore_from_snapshot(root: Path, snapshot: Path) -> None:
    """Best-effort rollback. Copies snapshot/ files back over root/, deletes
    files that the failed update added, and wipes any ``*.new`` staging
    artefacts. Uses ``shutil.copy2`` (not ``os.replace``) so the snapshot
    survives partial-rollback failures and remains usable for retries.
    """
    if not snapshot.is_dir():
        return
    snapshot_rels: set[str] = set()
    for path in snapshot.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(snapshot)
        snapshot_rels.add(rel.as_posix())
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(path, target)
        except OSError:
            # Locked or otherwise unwritable; leave the (possibly half-updated)
            # file as-is. The next successful update will reconcile it.
            continue

    # Delete files added by the failed update + any leftover .new markers.
    _sweep_files_not_in(root, snapshot_rels, sweep_pending_markers=True)


def _install_per_file(root: Path, archive_path: Path, manifest: dict) -> dict:
    """Install the new release into ``root`` via per-file overwrite.

    Steps:
        1. Extract zip into ``<parent>/<name>.staging`` (same volume as root).
        2. Flatten + verify the staged tree, then **collect the staged file
           set up-front** (commit consumes staging via ``os.replace``).
        3. Snapshot current files into ``<parent>/<name>.snapshot``.
        4. Seed PROTECTED defaults (e.g. config.json) on first install.
        5. Commit: replace each non-protected file in root.
        6. Sweep orphan files using the pre-collected staged set.
        7. Run pip install for runtime requirements.
        8. Persist version state (only after pip succeeds, so that on
           rollback the recorded version stays consistent with on-disk files).
        9. On any error: restore from snapshot.
       10. Cleanup staging + snapshot.
    """
    parent = root.parent
    staging = parent / f"{root.name}{STAGING_DIR_SUFFIX}"
    snapshot = parent / f"{root.name}{SNAPSHOT_DIR_SUFFIX}"

    _remove_existing_path(staging, label="stale staging directory")
    _remove_existing_path(snapshot, label="stale snapshot directory")
    staging.mkdir(parents=True)

    requirements_result: dict = {}
    pending: list[str] = []
    snapshot_committed = False
    seeded_rels: list[str] = []
    config_existed_before = (root / "config.json").is_file()

    try:
        _safe_zip_extractall(archive_path, staging)
        _flatten_extracted_root(staging)
        installed_version = _verify_skill_layout(staging)

        # Collect the set of incoming relative paths BEFORE commit, because
        # commit uses os.replace and physically moves files out of staging.
        # Without this, the subsequent sweep would think every successfully
        # committed file is an "orphan" and delete it from root.
        staged_rels = _collect_relative_files(staging)

        _snapshot_current_files(root, snapshot)
        snapshot_committed = True

        seeded_rels = _seed_protected_defaults(staging, root)
        pending = _commit_files_into_root(staging, root)
        _sweep_files_not_in(root, staged_rels)
        # Remove any *.new files that don't belong to the *current* pending
        # list — they're leftovers from older interrupted commits and would
        # otherwise accumulate forever.
        _sweep_dead_pending_markers(root, pending)

        if pending:
            _write_pending(root, pending)
        else:
            _clear_pending(root)

        _secure_local_config_if_present(root)
        requirements_result = _install_runtime_requirements(root)

        # Persist last so a pip failure leaves the state file pointing at the
        # old (still-on-disk) version after rollback.
        _persist_installed_version_state(
            root,
            version=installed_version,
            manifest_url=str(manifest.get("manifest_url") or ""),
            download_url=str(manifest.get("download_url") or ""),
        )

    except (Exception, KeyboardInterrupt, SystemExit):
        if snapshot_committed:
            _restore_from_snapshot(root, snapshot)
            # _restore_from_snapshot wipes all .new markers and any files
            # that the failed update added, but PROTECTED paths are skipped
            # by sweep — so seeded defaults need an explicit erase to keep
            # rollback byte-equivalent to the pre-update state.
            _erase_seeded(root, seeded_rels)
        # Pending list now refers to nothing — drop it.
        _clear_pending(root)
        raise
    finally:
        # Best-effort cleanup; do not mask the original exception.
        try:
            _remove_existing_path(staging, label="staging directory")
        except RuntimeError:
            pass
        try:
            _remove_existing_path(snapshot, label="snapshot directory")
        except RuntimeError:
            pass

    return {
        "installed_version": installed_version,
        "requirements": requirements_result,
        "pending_files": pending,
        "config_restored": config_existed_before and (root / "config.json").is_file(),
    }


# --------------------------------------------------------------------------- #
# Finalize: promote *.new files left over from a previous interrupted commit
# --------------------------------------------------------------------------- #

def finalize_pending(skill_dir: Path | None = None) -> dict:
    """Promote any ``<file>.new`` artefacts staged by an earlier run.

    Idempotent. Should be called at the start of every entry path so the
    skill converges to a consistent state without requiring user action.
    """
    root = (skill_dir or _detect_skill_dir()).resolve()
    pending = _read_pending(root)
    if not pending:
        return {"status": "no_pending"}

    # Process self_update.py last for the same reason commit does: avoid
    # swapping the running script out from under itself before the rest of
    # the work finishes. The pending list is otherwise persisted in sorted
    # order, so without this we'd promote the script in alphabetical
    # position — usually not last.
    self_update_name = Path(__file__).resolve().name
    pending_ordered = sorted(
        pending,
        key=lambda r: (Path(r) == Path(self_update_name), r),
    )

    promoted: list[str] = []
    still_pending: list[str] = []

    for rel in pending_ordered:
        rel_path = Path(rel)
        if _is_protected(rel_path):
            continue
        target = root / rel_path
        new_source = target.with_name(target.name + PENDING_SUFFIX)
        if not new_source.is_file():
            # Already promoted, or vanished — drop from the list.
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(new_source, target)
            promoted.append(rel)
        except OSError:
            still_pending.append(rel)

    if still_pending:
        _write_pending(root, still_pending)
    else:
        _clear_pending(root)

    return {
        "status": "finalized" if not still_pending else "partial",
        "promoted": promoted,
        "still_pending": still_pending,
    }


# --------------------------------------------------------------------------- #
# Legacy state migration (older self_update.py left .bak directories around)
# --------------------------------------------------------------------------- #

def _migrate_legacy_state(root: Path) -> None:
    """Clean up artefacts left by older self_update.py versions.

    - If root is intact and a sibling ``<name>.bak`` exists, remove it.
    - If root is incomplete and a sibling ``<name>.bak`` exists, restore it.
    """
    legacy_bak = root.with_name(root.name + ".bak")
    legacy_recovered = root.with_name(root.name + ".recovered-bak")

    root_intact = (
        (root / "SKILL.md").is_file()
        and (root / "scripts").is_dir()
        and (root / "api-docs" / "index.json").is_file()
    )

    if root_intact:
        for stale in (legacy_bak, legacy_recovered):
            if stale.exists():
                shutil.rmtree(stale, ignore_errors=True)
        return

    # Root is broken — try restoring from a legacy backup.
    source = next((p for p in (legacy_bak, legacy_recovered) if p.is_dir()), None)
    if source is None:
        return
    try:
        shutil.rmtree(root, ignore_errors=True)
        shutil.move(str(source), str(root))
    except OSError:
        # Best-effort; if this fails the user will see a clear error from
        # subsequent _verify_skill_layout calls.
        pass


# --------------------------------------------------------------------------- #
# Local config security
# --------------------------------------------------------------------------- #

def _secure_local_config_if_present(root: Path) -> None:
    config_path = root / "config.json"
    if config_path.is_file():
        _safe_chmod(config_path, 0o600)


# --------------------------------------------------------------------------- #
# Pip install
# --------------------------------------------------------------------------- #

def _extra_pip_install_args() -> list[str]:
    raw_value = str(os.environ.get(SELF_UPDATE_PIP_ARGS_ENV, "")).strip()
    if not raw_value:
        return []
    try:
        return shlex.split(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"invalid {SELF_UPDATE_PIP_ARGS_ENV}: {exc}") from exc


def _looks_like_externally_managed_failure(message: str) -> bool:
    normalized = str(message).lower()
    return (
        "externally-managed-environment" in normalized
        or "externally managed environment" in normalized
        or "externally managed" in normalized
    )


def _requirements_install_error_message(message: str) -> str:
    base_message = (
        "updated skill dependency install failed; rolling back skill files only "
        "(installed Python packages are not automatically uninstalled): "
    )
    if _looks_like_externally_managed_failure(message):
        return (
            base_message
            + "current Python environment is externally managed (PEP 668); "
            "rerun inside a writable virtual environment, or set "
            f"{SELF_UPDATE_PIP_ARGS_ENV}='--break-system-packages' if you explicitly want "
            f"the current interpreter to install packages anyway: {message}"
        )
    return base_message + message


def _install_runtime_requirements(skill_dir: Path) -> dict:
    requirements_path = skill_dir / "requirements.txt"
    if not requirements_path.is_file():
        return {
            "status": "skipped",
            "requirements_path": str(requirements_path),
            "reason": "requirements.txt not found",
        }

    extra_args = _extra_pip_install_args()
    command = [
        sys.executable, "-m", "pip", "install",
        *extra_args,
        "-r", str(requirements_path),
    ]
    completed = subprocess.run(
        command,
        cwd=str(skill_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "pip install failed").strip()
        raise RuntimeError(_requirements_install_error_message(message))

    return {
        "status": "installed",
        "requirements_path": str(requirements_path),
        "command": command,
    }


# --------------------------------------------------------------------------- #
# Top-level entry: self_update
# --------------------------------------------------------------------------- #

def self_update(
    manifest_url: str | None = None,
    skill_dir: Path | None = None,
    check_only: bool = False,
    base_url: str | None = None,
) -> dict:
    root = (skill_dir or _detect_skill_dir()).resolve()
    # Single coarse-grained lock for the entire run. finalize_pending is
    # called below without acquiring its own lock — we already hold it.
    with _exclusive_lock(root):
        _migrate_legacy_state(root)
        finalize_pending(root)

        local_ver = get_local_version(root)
        result: dict = {
            "local_version": local_ver,
            "remote_version": None,
            "download_url": None,
        }

        try:
            manifest = fetch_version_manifest(manifest_url, base_url=base_url)
        except RuntimeError as exc:
            if check_only:
                result["status"] = "check_failed"
                result["message"] = str(exc)
                result["continue_with_local_version"] = True
                return result
            raise

        remote_ver = manifest["version"]
        download_url = manifest["download_url"]
        result["remote_version"] = remote_ver
        result["download_url"] = download_url

        if _version_tuple(local_ver) >= _version_tuple(remote_ver):
            result["status"] = "up_to_date"
            return result

        if check_only:
            result["status"] = "update_available"
            return result

        archive_path = download_release(download_url)
        try:
            _verify_archive_digest(archive_path, manifest.get("sha256"))
            install_result = _install_per_file(root, archive_path, manifest)
        finally:
            _unlink_if_exists(archive_path)

        pending = install_result["pending_files"]
        result["status"] = "updated_with_pending" if pending else "updated"
        result["local_version"] = install_result["installed_version"]
        result["remote_version"] = install_result["installed_version"]
        result["requirements"] = install_result["requirements"]
        result["pending_files"] = pending
        result["config_restored"] = bool(install_result.get("config_restored"))
        if pending:
            result["message"] = (
                f"{len(pending)} file(s) were locked and staged as .new; they will "
                f"be promoted automatically the next time `python self_update.py "
                f"--finalize` runs (or on the next normal update)."
            )
        return result


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="User Skill self-updater")
    parser.add_argument(
        "--check",
        action="store_true",
        help="only check for an update, do not install",
    )
    parser.add_argument(
        "--finalize",
        action="store_true",
        help="promote any pending .new files from a previous update and exit",
    )
    parser.add_argument("--skill-dir", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    try:
        skill_dir = (
            Path(args.skill_dir).resolve() if args.skill_dir else _detect_skill_dir()
        )
        if args.finalize:
            with _exclusive_lock(skill_dir):
                _migrate_legacy_state(skill_dir)
                result = finalize_pending(skill_dir)
            print(json.dumps(result, ensure_ascii=False))
            return 0
        result = self_update(skill_dir=skill_dir, check_only=args.check)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(_main())
