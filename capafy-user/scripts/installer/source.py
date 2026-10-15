from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
from typing import Optional
import urllib.error
import urllib.request
import zipfile

from .archive import _detect_archive_format

try:
    from .. import auth
    from ..common import runtime_context
    from ..common.defaults import DEFAULT_PLATFORM_BASE_URL
except ImportError:  # pragma: no cover - install_package.py direct execution fallback
    import auth  # type: ignore
    from common import runtime_context  # type: ignore
    from common.defaults import DEFAULT_PLATFORM_BASE_URL  # type: ignore


def _resolve_base_url(base_url: str = "") -> str:
    if base_url:
        return base_url
    return str(
        os.environ.get("CAPAFY_PLATFORM_BASE_URL") or DEFAULT_PLATFORM_BASE_URL
    ).rstrip("/")


def _describe_non_archive_payload(path: Path) -> str:
    preview = path.read_bytes()[:4096]
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
    return msg or text[:200]


def _ensure_downloaded_archive(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError("package download failed: archive file missing")
    try:
        fmt = _detect_archive_format(path)
    except RuntimeError:
        detail = _describe_non_archive_payload(path)
        raise RuntimeError(
            f"package download returned non-archive payload: {detail}"
        ) from None
    try:
        if fmt == "zip":
            with zipfile.ZipFile(path) as archive:
                archive.namelist()
        else:
            with tarfile.open(path, "r:gz") as archive:
                archive.getmembers()
    except (tarfile.TarError, zipfile.BadZipFile, OSError):
        detail = _describe_non_archive_payload(path)
        raise RuntimeError(
            f"package download returned non-archive payload: {detail}"
        ) from None


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
) -> dict[str, Optional[str]]:
    resolved_base_url = _resolve_base_url(base_url)
    url = f"{resolved_base_url.rstrip('/')}/agent/orders/buyer/{order_id}/download"
    request = urllib.request.Request(
        url,
        headers=_build_platform_headers(access_token),
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode(errors="replace")
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
                raise RuntimeError(
                    f"order download failed: code={code}, msg={msg}"
                ) from None
        raise RuntimeError(f"order download failed: {exc.code}") from None

    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError("order download returned non-JSON response") from None
    data = body.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"order download returned unexpected response: {body}")

    metadata: dict[str, Optional[str]] = {"order_id": order_id}
    skill_install = data.get("skillInstall")
    if isinstance(skill_install, dict) and skill_install.get("url"):
        metadata["download_url"] = skill_install["url"]
        metadata["type"] = "download"
        if skill_install.get("licenseId") is not None:
            metadata["license_id"] = skill_install["licenseId"]
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
    url = f"{base_url.rstrip('/')}{path}"
    request = urllib.request.Request(
        url,
        headers=_build_platform_headers(access_token),
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode(errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace") if hasattr(exc, "read") else ""
        try:
            return {
                "__http_error__": exc.code,
                "__body__": json.loads(raw) if raw else None,
            }
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
) -> tuple[list[dict], set[str]]:
    collected: list[dict] = []
    seen: set[str] = set()
    failed_statuses: set[str] = set()
    target_agent = str(agent_id or "").strip()
    for status in ("active", "expired"):
        body = _fetch_platform_json(
            f"/agent/instance?status={status}",
            base_url=base_url,
            access_token=access_token,
        )
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            failed_statuses.add(status)
            continue
        items = data.get("instances") or []
        if not isinstance(items, list):
            failed_statuses.add(status)
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            item_agent_id = str(
                item.get("agent_id") or item.get("agentId") or ""
            ).strip()
            if target_agent and item_agent_id and item_agent_id != target_agent:
                continue
            instance_id = str(
                item.get("instance_id") or item.get("instanceId") or ""
            ).strip()
            if not instance_id or instance_id in seen:
                continue
            collected.append({
                "instance_id": instance_id,
                "instance_name": str(
                    item.get("name") or item.get("instance_name") or ""
                ).strip() or instance_id,
                "order_status": status,
            })
            seen.add(instance_id)
    return collected, failed_statuses


def _download_archive_from_url(url: str, destination: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/octet-stream"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        destination.write_bytes(response.read())


def download_package(
    order_id: str,
    *,
    base_url: str = "",
    access_token: Optional[str] = None,
) -> tuple[Path, dict[str, Optional[str]]]:
    resolved_base_url = _resolve_base_url(base_url)
    metadata = resolve_package_download_metadata(
        order_id,
        base_url=resolved_base_url,
        access_token=access_token,
    )
    download_url = metadata.get("download_url")
    if not download_url:
        raise RuntimeError("no download URL in order download response")

    tmp_dir = Path(tempfile.mkdtemp(prefix="capafy-package-"))
    suffix = ".zip" if ".zip" in download_url.lower() else ".tar.gz"
    archive_path = tmp_dir / f"{order_id}{suffix}"
    # The downloader owns its cache until successful return and cleans up network, format, digest, and interruption failures.
    try:
        _download_archive_from_url(download_url, archive_path)
        _ensure_downloaded_archive(archive_path)
        expected_sha256 = str(metadata.get("sha256") or "").strip().lower()
        if expected_sha256:
            actual_sha256 = hashlib.sha256(archive_path.read_bytes()).hexdigest()
            if actual_sha256 != expected_sha256:
                raise RuntimeError(
                    f"package download sha256 mismatch: expected {expected_sha256}, "
                    f"got {actual_sha256}"
                )
    except BaseException:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    return archive_path, metadata
