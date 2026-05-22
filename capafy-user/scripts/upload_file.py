from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    from . import capafy_http
except ImportError:  # pragma: no cover - CLI fallback
    import capafy_http  # type: ignore


DEFAULT_BIZ_TYPE = "buyer_agent"


def _normalize_base_url(base_url: str = "") -> str:
    return capafy_http._normalize_platform_base_url(base_url)


def _guess_content_type(file_path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(file_path))
    return mime or "application/octet-stream"


def get_presign_upload(
    file_name: str,
    content_type: str,
    *,
    biz_type: str = DEFAULT_BIZ_TYPE,
    base_url: str = "",
) -> dict:
    """Call presign upload API, return response data dict."""
    base_url = _normalize_base_url(base_url)
    url = f"{base_url.rstrip('/')}/agent/file/presign/upload"
    body, status = capafy_http.request(
        "POST",
        url,
        json_body={
            "fileName": file_name,
            "contentType": content_type,
            "bizType": biz_type,
        },
        auto_platform_auth=True,
        platform_base_url=base_url,
    )
    if status >= 400 or not isinstance(body, dict):
        raise RuntimeError(f"presign upload failed: {status} {body}")
    data = body.get("data")
    if not isinstance(data, dict) or not data.get("uploadUrl"):
        raise RuntimeError(f"presign upload returned unexpected response: {body}")
    return data


def put_to_s3(upload_url: str, file_path: Path, content_type: str, headers: dict | None = None) -> int:
    """PUT file bytes to the presigned S3 URL. Returns HTTP status."""
    file_bytes = file_path.read_bytes()
    all_headers = {"Content-Type": content_type}
    if headers:
        all_headers.update(headers)
    req = urllib.request.Request(
        upload_url,
        data=file_bytes,
        headers=all_headers,
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"S3 upload failed: {exc.code} {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"S3 upload connection failed: {exc.reason}") from exc


def get_download_presign(object_key: str, *, base_url: str = "") -> dict:
    """Call presign download API, return response data dict."""
    base_url = _normalize_base_url(base_url)
    url = f"{base_url.rstrip('/')}/agent/file/presign/download"
    body, status = capafy_http.request(
        "POST",
        url,
        json_body={"objectKey": object_key},
        auto_platform_auth=True,
        platform_base_url=base_url,
    )
    if status >= 400 or not isinstance(body, dict):
        raise RuntimeError(f"presign download failed: {status} {body}")
    data = body.get("data")
    if not isinstance(data, dict) or not data.get("downloadUrl"):
        raise RuntimeError(f"presign download returned unexpected response: {body}")
    return data


def upload_file(
    file_path: Path,
    *,
    biz_type: str = DEFAULT_BIZ_TYPE,
    base_url: str = "",
    include_download_url: bool = False,
) -> dict:
    """Full upload flow: presign → PUT to S3 → return result."""
    if not file_path.is_file():
        raise RuntimeError(f"file not found: {file_path}")

    base_url = _normalize_base_url(base_url)
    content_type = _guess_content_type(file_path)

    # Step 1: get presigned URL
    presign = get_presign_upload(
        file_path.name,
        content_type,
        biz_type=biz_type,
        base_url=base_url,
    )

    # Step 2: PUT to S3
    put_to_s3(
        presign["uploadUrl"],
        file_path,
        content_type,
        headers=presign.get("headers"),
    )

    # Step 3: build result
    result = {
        "objectKey": presign.get("objectKey", ""),
        "fileName": file_path.name,
        "contentType": content_type,
        "sizeBytes": file_path.stat().st_size,
        "publicUrl": presign.get("publicUrl"),
    }

    # Only expose a stable URL by default. Temporary download URLs are opt-in.
    public_url = presign.get("publicUrl")
    if public_url:
        result["url"] = public_url
    elif include_download_url:
        download_presign = get_download_presign(presign["objectKey"], base_url=base_url)
        result["downloadUrl"] = download_presign["downloadUrl"]
        expires = download_presign.get("expiresInSeconds")
        if expires not in (None, ""):
            result["downloadUrlExpiresInSeconds"] = expires

    return result


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Upload file to capafy platform")
    parser.add_argument("file", help="path to the file to upload")
    parser.add_argument("--biz-type", default=DEFAULT_BIZ_TYPE)
    parser.add_argument("--base-url", default="")
    parser.add_argument(
        "--include-download-url",
        action="store_true",
        help="include a temporary downloadUrl when publicUrl is unavailable",
    )
    args = parser.parse_args(argv)

    try:
        result = upload_file(
            Path(args.file),
            biz_type=args.biz_type,
            base_url=args.base_url,
            include_download_url=args.include_download_url,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except RuntimeError as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(_main())
