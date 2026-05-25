from __future__ import annotations

import urllib.error
import urllib.request
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Optional, Union
from urllib.parse import urlparse, urlunparse

from capafy_platform.defaults import (
    DEFAULT_PACKAGE_BIZ_TYPE,
    DEFAULT_PACKAGE_CONTENT_TYPE,
    DEFAULT_UPLOAD_TIMEOUT_SECONDS,
)
from capafy_platform.http import post_platform_json
from packaging._shared.common.fs import normalize_path
from packaging._shared.common.url_values import has_http_url_scheme


def build_file_upload_presign_request(
    file_name: str,
    *,
    agent_version_id: str,
    content_type: str,
    biz_type: Optional[str] = None,
) -> dict[str, str]:
    normalized_agent_version_id = str(agent_version_id or "").strip()
    if not normalized_agent_version_id:
        raise ValueError("agent_version_id must not be empty")

    normalized_file_name = str(file_name or "").strip()
    if not normalized_file_name:
        raise ValueError("file_name must not be empty")

    normalized_content_type = str(content_type or "").strip()
    if not normalized_content_type:
        raise ValueError("content_type must not be empty")

    payload = {
        "agentVersionId": normalized_agent_version_id,
        "fileName": normalized_file_name,
        "contentType": normalized_content_type,
    }
    normalized_biz_type = str(biz_type or "").strip()
    if normalized_biz_type:
        payload["bizType"] = normalized_biz_type
    return payload


def _normalize_presign_headers(raw_headers: object) -> dict[str, str]:
    if raw_headers in (None, ""):
        return {}
    if not isinstance(raw_headers, dict):
        raise ValueError("file upload presign response headers must be an object")
    headers: dict[str, str] = {}
    for raw_key, raw_value in raw_headers.items():
        key = str(raw_key or "").strip()
        value = str(raw_value or "").strip()
        if key and value:
            headers[key] = value
    return headers


def _normalize_upload_presign_response(
    request_body: dict[str, str],
    data: dict[str, Any],
) -> dict[str, Any]:
    upload_url = str(data.get("uploadUrl", "")).strip()
    if not upload_url:
        raise ValueError("file upload presign response is missing uploadUrl")

    object_key = str(data.get("objectKey", "")).strip()
    if not object_key:
        raise ValueError("file upload presign response is missing objectKey")
    upload_method = str(data.get("uploadMethod", "PUT") or "PUT").strip().upper() or "PUT"

    raw_public_url = data.get("publicUrl")
    public_url = "" if raw_public_url is None else str(raw_public_url).strip()
    derived_http_url = _derive_http_package_url(upload_url, object_key)
    if has_http_url_scheme(public_url):
        package_url = public_url
        package_url_source = "public_url"
    elif derived_http_url:
        package_url = derived_http_url
        package_url_source = "derived_http_url"
    else:
        raise ValueError("file upload presign response must provide an absolute http(s) package URL")

    result = dict(data)
    result["api_action"] = "file_presign_upload"
    result["request_body"] = request_body
    result["headers"] = _normalize_presign_headers(data.get("headers"))
    result["upload_url"] = upload_url
    result["upload_method"] = upload_method
    result["object_key"] = object_key
    result["public_url"] = public_url
    result["derived_http_url"] = derived_http_url
    result["package_url"] = package_url
    result["package_url_source"] = package_url_source
    return result


def _derive_http_package_url(upload_url: str, object_key: str) -> str:
    normalized_upload_url = str(upload_url or "").strip()
    if not has_http_url_scheme(normalized_upload_url):
        return ""
    parsed = urlparse(normalized_upload_url)
    if not parsed.scheme or not parsed.netloc:
        return ""

    normalized_object_key = str(object_key or "").strip().lstrip("/")
    if not normalized_object_key:
        return ""

    path = parsed.path or ""
    if path.endswith(f"/{normalized_object_key}"):
        normalized_path = path
    else:
        normalized_path = f"/{normalized_object_key}"

    return urlunparse((parsed.scheme, parsed.netloc, normalized_path, "", "", ""))


def presign_file_upload(
    file_name: str,
    *,
    agent_version_id: str,
    content_type: str,
    biz_type: Optional[str] = None,
    access_token: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict[str, Any]:
    request_body = build_file_upload_presign_request(
        file_name,
        agent_version_id=agent_version_id,
        content_type=content_type,
        biz_type=biz_type,
    )
    data = post_platform_json(
        "/agent/file/presign/upload",
        request_body,
        base_url=base_url,
        access_token=access_token,
        require_auth=True,
    )
    return _normalize_upload_presign_response(request_body, data)


def upload_file_to_presigned_url(
    file_path: Union[str, Path],
    upload_url: str,
    *,
    headers: Optional[dict[str, str]] = None,
    method: str = "PUT",
    timeout_seconds: float = DEFAULT_UPLOAD_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    normalized_file_path = normalize_path(file_path)
    if not normalized_file_path.is_file():
        raise ValueError(f"upload file does not exist: {normalized_file_path}")

    normalized_method = str(method or "PUT").strip().upper() or "PUT"
    if normalized_method != "PUT":
        raise ValueError(f"only PUT presigned uploads are currently supported: {normalized_method}")

    request_headers = {str(key): str(value) for key, value in (headers or {}).items()}
    if not any(str(key).lower() == "content-length" for key in request_headers):
        request_headers["Content-Length"] = str(normalized_file_path.stat().st_size)
    try:
        with ExitStack() as stack:
            body = stack.enter_context(normalized_file_path.open("rb"))
            request = urllib.request.Request(
                str(upload_url).strip(),
                data=body,
                headers=request_headers,
                method=normalized_method,
            )
            response = stack.enter_context(urllib.request.urlopen(request, timeout=timeout_seconds))
            return {
                "upload_status": response.status,
                "upload_response_headers": dict(response.headers.items()),
            }
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace").strip()
        message = f"presigned upload failed: HTTP {exc.code}"
        if body:
            message = f"{message}: {body}"
        raise ValueError(message) from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"presigned upload failed: {exc.reason}") from exc


def upload_package_bundle(
    bundle_file: Union[str, Path],
    *,
    agent_version_id: str,
    access_token: Optional[str] = None,
    base_url: Optional[str] = None,
    biz_type: str = DEFAULT_PACKAGE_BIZ_TYPE,
    content_type: str = DEFAULT_PACKAGE_CONTENT_TYPE,
) -> dict[str, Any]:
    normalized_bundle_file = normalize_path(bundle_file)
    if not normalized_bundle_file.is_file():
        raise ValueError(f"bundle_file does not exist: {normalized_bundle_file}")
    if normalized_bundle_file.suffix.lower() != ".zip":
        raise ValueError(f"bundle_file must be a .zip file: {normalized_bundle_file}")


    presign_payload = presign_file_upload(
        normalized_bundle_file.name,
        agent_version_id=agent_version_id,
        content_type=content_type,
        biz_type=biz_type,
        access_token=access_token,
        base_url=base_url,
    )
    upload_payload = upload_file_to_presigned_url(
        normalized_bundle_file,
        presign_payload["upload_url"],
        headers=presign_payload["headers"],
        method=str(presign_payload.get("upload_method", "PUT") or "PUT").strip().upper(),
    )
    return {
        "api_action": "upload_package_bundle",
        "bundle_file": str(normalized_bundle_file),
        "file_name": normalized_bundle_file.name,
        "file_size_bytes": normalized_bundle_file.stat().st_size,
        "content_type": content_type,
        "biz_type": biz_type,
        **presign_payload,
        **upload_payload,
        "uploaded": True,
    }


__all__ = [
    "build_file_upload_presign_request",
    "presign_file_upload",
    "upload_file_to_presigned_url",
    "upload_package_bundle",
]
