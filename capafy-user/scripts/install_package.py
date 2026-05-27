from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import sys
from typing import Optional
import urllib.error
import urllib.request
import zipfile

try:
    from . import auth, runtime_context
    from . import thin_skill_state
    from .defaults import DEFAULT_PLATFORM_BASE_URL
except ImportError:  # pragma: no cover - CLI fallback
    import auth  # type: ignore
    import runtime_context  # type: ignore
    import thin_skill_state  # type: ignore
    from defaults import DEFAULT_PLATFORM_BASE_URL  # type: ignore


ENV_PATTERNS = (
    re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}"),
    re.compile(r"process\.env\.([A-Z][A-Z0-9_]*)"),
    re.compile(r"os\.environ\[\s*['\"]([A-Z][A-Z0-9_]*)['\"]\s*\]"),
    re.compile(r"os\.getenv\(\s*['\"]([A-Z][A-Z0-9_]*)['\"]\s*\)"),
)
SKILL_NAME_PATTERN = re.compile(r"(?m)^name:\s*(.+?)\s*$")


def verify_sha256(path: Path, expected: str) -> bool:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest == expected


def detect_install_root(script_path: Optional[Path] = None) -> Path:
    current = Path(script_path) if script_path is not None else Path(__file__).resolve()
    for parent in current.parents:
        if parent.name == "skills":
            return parent
    raise RuntimeError(
        "unable to determine install root from current user skill location; pass --install-root"
    )


def _resolve_base_url(base_url: str = "") -> str:
    if base_url:
        return base_url
    return DEFAULT_PLATFORM_BASE_URL


def _detect_archive_format(archive_path: Path) -> str:
    with archive_path.open("rb") as fp:
        head = fp.read(4)
    if head[:2] == b"PK":
        return "zip"
    if head[:2] == b"\x1f\x8b":
        return "tar.gz"
    raise RuntimeError(f"unsupported archive format: {archive_path}")


def extract_archive(archive_path: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    fmt = _detect_archive_format(archive_path)
    if fmt == "zip":
        with zipfile.ZipFile(archive_path) as zf:
            zf.extractall(destination)
    else:
        with tarfile.open(archive_path, "r:gz") as tar:
            try:
                tar.extractall(destination, filter="data")
            except TypeError:
                tar.extractall(destination)
    children = [item for item in destination.iterdir()]
    return children[0] if len(children) == 1 else destination


def _normalize_skill_dir_name(raw_name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", raw_name.strip()).strip(".-")
    if not normalized:
        raise RuntimeError("unable to determine safe install directory name from package metadata")
    return normalized


def _read_skill_name(package_root: Path) -> Optional[str]:
    skill_md = package_root / "SKILL.md"
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return None

    # Only search within YAML frontmatter (between --- delimiters)
    # Strip UTF-8 BOM and normalize CRLF so creator-authored files parse correctly
    text = text.lstrip("\ufeff").replace("\r\n", "\n")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            frontmatter = text[3:end]
            match = SKILL_NAME_PATTERN.search(frontmatter)
            if match:
                return _normalize_skill_dir_name(match.group(1))
    return None


def _read_archive_top_levels(archive_path: Path) -> list[str]:
    fmt = _detect_archive_format(archive_path)
    if fmt == "zip":
        with zipfile.ZipFile(archive_path) as zf:
            top_levels = {
                name.split("/")[0]
                for name in zf.namelist()
                if name and name not in {".", "./"}
            }
    else:
        with tarfile.open(archive_path, "r:gz") as tar:
            top_levels = {
                member.name.split("/")[0]
                for member in tar.getmembers()
                if member.name and member.name not in {".", "./"}
            }
    return sorted(top_levels)


def resolve_install_dir_name(
    package_root: Path,
    *,
    archive_path: Optional[Path] = None,
) -> str:
    validate_package_layout(package_root)

    skill_name = _read_skill_name(package_root)
    if skill_name:
        return skill_name

    if archive_path is not None:
        top_levels = _read_archive_top_levels(archive_path)
        if len(top_levels) == 1:
            return _normalize_skill_dir_name(top_levels[0])
        raise RuntimeError(
            "unable to determine safe install directory name from package; "
            "add 'name:' to SKILL.md frontmatter or package the skill under a top-level directory"
        )

    return _normalize_skill_dir_name(package_root.name)


def resolve_install_target(
    package_root: Path,
    install_root: Path,
    *,
    archive_path: Optional[Path] = None,
) -> Path:
    install_dir_name = resolve_install_dir_name(package_root, archive_path=archive_path)
    target = install_root / install_dir_name
    if target == install_root:
        raise RuntimeError("refusing to install package directly into skills root")
    return target


def install_from_file(archive_path: Path, destination_root: Optional[Path] = None) -> Path:
    install_root = destination_root or detect_install_root()
    install_root.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix="capafy-install-"))
    try:
        package_root = extract_archive(archive_path, staging_dir / "extract")
        target = resolve_install_target(package_root, install_root, archive_path=archive_path)
        if target.exists():
            raise FileExistsError(f"target already exists: {target}")
        shutil.copytree(package_root, target)
        return target
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


def collect_env_vars_needed(package_root: Path) -> list[str]:
    names: set[str] = set()
    for path in package_root.rglob("*"):
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
    commands: list[tuple[list[str], Path]] = []
    requirements_path = package_root / "requirements.txt"
    package_json_path = package_root / "package.json"

    if requirements_path.is_file():
        commands.append((["python3", "-m", "pip", "install", "-r", str(requirements_path)], package_root))
    if package_json_path.is_file():
        commands.append((["npm", "install"], package_root))

    execute = runner or _default_runner
    deps_ok = True
    missing_deps: set[str] = set()

    if not execute_installers:
        for cmd, _cwd in commands:
            if shutil.which(cmd[0]) is None:
                deps_ok = False
                missing_deps.add(cmd[0])
        return {
            "deps_ok": deps_ok,
            "missing_deps": sorted(missing_deps),
        }

    for cmd, cwd in commands:
        try:
            execute(cmd, cwd)
        except FileNotFoundError:
            deps_ok = False
            missing_deps.add(cmd[0])
        except subprocess.CalledProcessError:
            deps_ok = False
            missing_deps.add(cmd[0])

    return {
        "deps_ok": deps_ok,
        "missing_deps": sorted(missing_deps),
    }


def inspect_install_target(
    package_root: Path,
    runner=None,
    *,
    execute_installers: bool = True,
    install_root: Optional[Path] = None,
    archive_path: Optional[Path] = None,
) -> dict[str, object]:
    validate_package_layout(package_root)
    install_report = install_dependencies(
        package_root,
        runner=runner,
        execute_installers=execute_installers,
    )
    install_report["env_vars_needed"] = collect_env_vars_needed(package_root)
    if install_root is not None:
        install_report["install_target"] = str(
            resolve_install_target(package_root, install_root, archive_path=archive_path)
        )
    return install_report


def validate_package_layout(package_root: Path) -> None:
    if not package_root.exists() or not package_root.is_dir():
        raise RuntimeError(f"invalid package directory: {package_root}")
    if not (package_root / "SKILL.md").is_file():
        raise RuntimeError(f"invalid package layout: missing SKILL.md in {package_root}")


def _describe_non_archive_payload(path: Path) -> str:
    raw = path.read_bytes()
    preview = raw[:4096]
    try:
        text = preview.decode("utf-8").strip()
    except UnicodeDecodeError:
        return "non-archive payload"
    if not text:
        return "empty payload"
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text[:200]
    if not isinstance(payload, dict):
        return text[:200]
    code = payload.get("code")
    msg = str(payload.get("msg", "")).strip()
    if code is not None and msg:
        return f"code={code}, msg={msg}"
    if msg:
        return msg
    return text[:200]


def _ensure_downloaded_archive(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError("package download failed: archive file missing")
    try:
        fmt = _detect_archive_format(path)
    except RuntimeError:
        detail = _describe_non_archive_payload(path)
        raise RuntimeError(f"package download returned non-archive payload: {detail}") from None
    try:
        if fmt == "zip":
            with zipfile.ZipFile(path) as zf:
                zf.namelist()
        else:
            with tarfile.open(path, "r:gz") as tar:
                tar.getmembers()
    except (tarfile.TarError, zipfile.BadZipFile, OSError):
        detail = _describe_non_archive_payload(path)
        raise RuntimeError(f"package download returned non-archive payload: {detail}") from None


def _build_platform_headers(access_token: Optional[str] = None) -> dict[str, str]:
    token = str(access_token or "").strip()
    if not token:
        try:
            token = str(auth.load_token() or "").strip()
        except ValueError:
            token = ""
    headers = {"Accept": "application/json"}
    headers.update(runtime_context.platform_context_headers())
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def resolve_package_download_metadata(
    order_id: str,
    *,
    base_url: str = "",
    access_token: Optional[str] = None,
    app_version_id: Optional[str] = None,
) -> dict[str, Optional[str]]:
    """Call GET /agent/orders/buyer/{orderId}/download and return metadata."""
    resolved_base_url = _resolve_base_url(base_url)
    url = f"{resolved_base_url.rstrip('/')}/agent/orders/buyer/{order_id}/download"
    if app_version_id:
        url = f"{url}?appVersionId={app_version_id}"
    req = urllib.request.Request(
        url,
        headers=_build_platform_headers(access_token),
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode(errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw
        if isinstance(payload, dict):
            code = payload.get("code")
            msg = str(payload.get("msg", "")).strip()
            if code is not None and msg:
                raise RuntimeError(f"order download failed: code={code}, msg={msg}") from None
        raise RuntimeError(f"order download failed: {exc.code}") from None

    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError(f"order download returned non-JSON response")

    data = body.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"order download returned unexpected response: {body}")

    metadata: dict[str, Optional[str]] = {"order_id": order_id}

    skill_install = data.get("skillInstall")
    if isinstance(skill_install, dict) and skill_install.get("url"):
        metadata["download_url"] = skill_install["url"]
        metadata["type"] = "download"
        return metadata

    thin_template = data.get("thinSkillTemplate")
    if isinstance(thin_template, dict) and thin_template.get("downloadUrl"):
        metadata["download_url"] = thin_template["downloadUrl"]
        metadata["type"] = "thin_skill"
        metadata["thin_skill_template_id"] = thin_template.get("thinSkillTemplateId")
        metadata["folder_name"] = thin_template.get("folderName")
        metadata["sha256"] = thin_template.get("sha256")
        return metadata

    raise RuntimeError(f"order download returned no installable content: {body}")


def _fetch_platform_json(
    path: str,
    *,
    base_url: str,
    access_token: Optional[str] = None,
) -> dict:
    """GET a JSON response from the platform. Returns the parsed body (may be empty on error)."""
    url = f"{base_url.rstrip('/')}{path}"
    req = urllib.request.Request(
        url,
        headers=_build_platform_headers(access_token),
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode(errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace") if hasattr(exc, "read") else ""
        try:
            return {"__http_error__": exc.code, "__body__": json.loads(raw) if raw else None}
        except json.JSONDecodeError:
            return {"__http_error__": exc.code, "__body__": raw}
    except urllib.error.URLError as exc:
        return {"__network_error__": str(getattr(exc, "reason", exc))}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _fetch_order_detail(
    order_id: str,
    *,
    base_url: str,
    access_token: Optional[str] = None,
) -> dict[str, str]:
    """GET /agent/orders/buyer/{orderId}/detail. Returns {agent_id, instance_id, agent_title}."""
    body = _fetch_platform_json(
        f"/agent/orders/buyer/{order_id}/detail",
        base_url=base_url,
        access_token=access_token,
    )
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        return {}
    return {
        "agent_id": str(data.get("agentId") or "").strip(),
        "instance_id": str(data.get("instanceId") or "").strip(),
        "agent_title": str(data.get("agentTitle") or "").strip(),
    }


def _fetch_agent_instances(
    agent_id: str,
    *,
    base_url: str,
    access_token: Optional[str] = None,
    statuses: tuple[str, ...] = ("active", "expired"),
) -> list[dict]:
    """Fetch instances across statuses and filter to one agent. Returns [] on network error."""
    collected: list[dict] = []
    seen: set[str] = set()
    target_agent = str(agent_id or "").strip()
    for status in statuses:
        body = _fetch_platform_json(
            f"/agent/instance?status={status}",
            base_url=base_url,
            access_token=access_token,
        )
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            continue
        items = data.get("instances") or []
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            item_agent_id = str(item.get("agent_id") or item.get("agentId") or "").strip()
            if target_agent and item_agent_id and item_agent_id != target_agent:
                continue
            instance_id = str(item.get("instance_id") or item.get("instanceId") or "").strip()
            if not instance_id or instance_id in seen:
                continue
            collected.append({
                "instance_id": instance_id,
                "instance_name": str(item.get("name") or item.get("instance_name") or "").strip() or instance_id,
                "order_status": status,
            })
            seen.add(instance_id)
    return collected


def _derive_agent_id_from_folder(folder_name: Optional[str]) -> str:
    value = str(folder_name or "").strip()
    prefix = "capafy-agent-"
    if value.startswith(prefix):
        return value[len(prefix):]
    return ""


def sync_thin_skill_state_after_install(
    order_id: str,
    metadata: dict,
    installed_to: Path,
    *,
    base_url: str,
    access_token: Optional[str] = None,
) -> dict:
    """After installing a thin skill, auto-populate thin_skills_state.json.

    Best-effort: any failure returns {synced: false, reason: ...} without raising,
    so the install itself is not rolled back. Caller embeds result into report.
    """
    resolved_base_url = _resolve_base_url(base_url)

    # 1) Resolve agent_id + purchased instance_id via order detail (authoritative).
    #    Fall back to folder_name-derived agent_id if the detail call fails.
    order_detail: dict[str, str] = {}
    try:
        order_detail = _fetch_order_detail(
            order_id,
            base_url=resolved_base_url,
            access_token=access_token,
        )
    except Exception as exc:  # pragma: no cover - defensive, urllib may raise unexpected
        order_detail = {}
        detail_error = str(exc)
    else:
        detail_error = ""

    agent_id = order_detail.get("agent_id") or _derive_agent_id_from_folder(metadata.get("folder_name"))
    purchased_instance_id = order_detail.get("instance_id") or ""

    if not agent_id:
        return {
            "synced": False,
            "reason": "unable_to_determine_agent_id",
            "order_detail_error": detail_error,
        }

    # 2) Pull fresh instance list for this agent. If the API call fails or returns
    #    nothing but we do have the newly-purchased instance_id, fall back to a
    #    single-instance list so the state at least reflects this order.
    instances = _fetch_agent_instances(
        agent_id,
        base_url=resolved_base_url,
        access_token=access_token,
    )
    if not instances and purchased_instance_id:
        instances = [{
            "instance_id": purchased_instance_id,
            "instance_name": order_detail.get("agent_title") or purchased_instance_id,
            "order_status": "active",
        }]

    if not instances:
        return {
            "synced": False,
            "reason": "no_instances_found",
            "agent_id": agent_id,
        }

    # 3) Persist via thin_skill_state.sync_agent_state.
    try:
        agent_state = thin_skill_state.sync_agent_state(
            agent_id,
            instances=instances,
            default_instance_id=purchased_instance_id or None,
            thin_skill_template_id=metadata.get("thin_skill_template_id"),
            order_id=order_id,
            thin_skill_dir=str(installed_to),
            initialize_last_used_instance_id=purchased_instance_id or None,
        )
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "synced": False,
            "reason": f"sync_agent_state_failed: {exc}",
            "agent_id": agent_id,
        }

    if agent_state is None:
        return {
            "synced": False,
            "reason": "sync_agent_state_returned_none",
            "agent_id": agent_id,
        }

    return {
        "synced": True,
        "agent_id": agent_id,
        "default_instance_id": agent_state.get("default_instance_id"),
        "default_instance_name": agent_state.get("default_instance_name"),
        "thin_skill_dir": agent_state.get("thin_skill_dir"),
        "instance_count": len(agent_state.get("instances") or []),
    }


def resolve_package_download_url(
    order_id: str,
    *,
    base_url: str = "",
    access_token: Optional[str] = None,
) -> str:
    metadata = resolve_package_download_metadata(
        order_id,
        base_url=base_url,
        access_token=access_token,
    )
    url = metadata.get("download_url")
    if not url:
        raise RuntimeError("no download URL in order download response")
    return url


def _download_archive_from_url(url: str, destination: Path) -> None:
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/octet-stream"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        destination.write_bytes(resp.read())


def download_package(
    order_id: str,
    *,
    base_url: str = "",
    access_token: Optional[str] = None,
    app_version_id: Optional[str] = None,
) -> tuple[Path, dict[str, Optional[str]]]:
    """Download package for an order. Returns (archive_path, metadata)."""
    resolved_base_url = _resolve_base_url(base_url)
    metadata = resolve_package_download_metadata(
        order_id,
        base_url=resolved_base_url,
        access_token=access_token,
        app_version_id=app_version_id,
    )
    download_url = metadata.get("download_url")
    if not download_url:
        raise RuntimeError("no download URL in order download response")

    tmp_dir = Path(tempfile.mkdtemp(prefix="capafy-package-"))
    suffix = ".zip" if ".zip" in download_url.lower() else ".tar.gz"
    archive_path = tmp_dir / f"{order_id}{suffix}"
    _download_archive_from_url(download_url, archive_path)
    _ensure_downloaded_archive(archive_path)
    return archive_path, metadata


def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="User Skill package installer")
    parser.add_argument("--order-id", dest="order_id")
    parser.add_argument("--app-version-id", dest="app_version_id", default=None)
    parser.add_argument("--file")
    parser.add_argument("--check-deps", dest="check_deps")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--install-root", default="")
    args = parser.parse_args(argv)

    try:
        if args.check_deps:
            target = Path(args.check_deps)
            if target.exists():
                print(json.dumps(inspect_install_target(target)))
            else:
                print('{"deps_ok": true, "missing_deps": [], "env_vars_needed": []}')
            return 0

        if args.file:
            archive_path = Path(args.file)
            destination_root = Path(args.install_root).expanduser() if args.install_root else None
            target = install_from_file(archive_path, destination_root=destination_root)
            report = inspect_install_target(target)
            report["installed_to"] = str(target)
            print(json.dumps(report))
            return 0

        if not args.order_id:
            parser.error("--order-id or --file is required")

        archive_path, metadata = download_package(
            args.order_id,
            base_url=args.base_url,
            app_version_id=args.app_version_id,
        )
        try:
            destination_root = Path(args.install_root).expanduser() if args.install_root else None
            target = install_from_file(archive_path, destination_root=destination_root)
        finally:
            tmp_dir = archive_path.parent
            shutil.rmtree(tmp_dir, ignore_errors=True)
        report = inspect_install_target(target)
        report["installed_to"] = str(target)
        if metadata.get("type"):
            report["package_type"] = metadata["type"]
        if metadata.get("thin_skill_template_id"):
            report["thin_skill_template_id"] = metadata["thin_skill_template_id"]

        # For thin skills (Run Online orders), auto-persist thin_skills_state.json
        # so future dialog turns can find the installed shortcut without a manual
        # state-update step. Best-effort: failures are reported but don't roll back.
        if metadata.get("type") == "thin_skill":
            report["state_sync"] = sync_thin_skill_state_after_install(
                args.order_id,
                metadata,
                target,
                base_url=args.base_url,
            )

        print(json.dumps(report))
        return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(_main())
