from __future__ import annotations

import argparse
import json
import mimetypes
import os
from pathlib import Path
import sys
from typing import Optional
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import uuid

try:
    from . import auth, runtime_context
    from .defaults import DEFAULT_PLATFORM_BASE_URL
except ImportError:  # pragma: no cover - CLI fallback
    import auth  # type: ignore
    import runtime_context  # type: ignore
    from defaults import DEFAULT_PLATFORM_BASE_URL  # type: ignore


PLATFORM_BASE_URL_ENV = "CAPAFY_PLATFORM_BASE_URL"
EXPLICIT_AUTH_HEADER_KEYS = {"authorization", "x-access-token"}
SKILL_VERSION_STATUS_HEADER = "X-Skill-Version-Status"


def _normalize_headers(headers: dict[str, str] | None) -> dict[str, str]:
    return dict(headers or {})


def platform_context_headers() -> dict[str, str]:
    return runtime_context.platform_context_headers()


def _maybe_inject_platform_context_headers(
    url: str,
    headers: dict[str, str],
    *,
    platform_base_url: Optional[str] = None,
    force: bool = False,
) -> None:
    if not force and not _is_platform_request(url, platform_base_url=platform_base_url):
        return
    for key, value in runtime_context.platform_context_headers().items():
        headers.setdefault(key, value)


def _normalize_platform_base_url(base_url: Optional[str] = None) -> str:
    candidate = str(base_url or os.environ.get(PLATFORM_BASE_URL_ENV) or "").strip()
    if not candidate:
        candidate = DEFAULT_PLATFORM_BASE_URL
    if not candidate:
        return ""
    if "://" not in candidate:
        candidate = f"http://{candidate}"
    return candidate.rstrip("/")


def _origin_parts(url: str) -> tuple[str, int]:
    parsed = urlsplit(url if "://" in url else f"http://{url}")
    host = str(parsed.hostname or "").lower().strip()
    scheme = str(parsed.scheme or "http").lower()
    port = parsed.port
    if port is None:
        port = 443 if scheme == "https" else 80
    return host, port


def _is_platform_request(url: str, *, platform_base_url: Optional[str] = None) -> bool:
    normalized_base_url = _normalize_platform_base_url(platform_base_url)
    if not normalized_base_url:
        return False
    return _origin_parts(url) == _origin_parts(normalized_base_url)


def _has_explicit_auth_header(headers: dict[str, str]) -> bool:
    return any(str(key).strip().lower() in EXPLICIT_AUTH_HEADER_KEYS for key in headers)


def _resolve_platform_access_token(
    access_token: Optional[str] = None,
    *,
    auth_loader=None,
) -> tuple[str, str] | tuple[None, None]:
    explicit_token = str(access_token or "").strip()
    if explicit_token:
        return explicit_token, "explicit_access_token"

    if auth_loader is not None:
        try:
            loaded_token = str(auth_loader() or "").strip()
        except ValueError as exc:
            print(f"[http] token loader failed: {exc}", file=sys.stderr)
            return None, None
        if loaded_token:
            return loaded_token, "custom_auth_loader"
        return None, None

    try:
        loaded_token = auth.load_token()
    except ValueError as exc:
        print(f"[http] local platform token load failed: {exc}", file=sys.stderr)
        return None, None
    if not loaded_token:
        return None, None
    if os.environ.get(auth.PLATFORM_ACCESS_TOKEN_ENV, "").strip():
        return loaded_token, auth.PLATFORM_ACCESS_TOKEN_ENV
    if os.environ.get(auth.TOKEN_ENV_VAR, "").strip():
        return loaded_token, auth.TOKEN_ENV_VAR
    return loaded_token, "persisted_platform_token"


def _maybe_inject_platform_auth_header(
    url: str,
    headers: dict[str, str],
    *,
    auto_platform_auth: bool = False,
    access_token: Optional[str] = None,
    platform_base_url: Optional[str] = None,
    auth_loader=None,
) -> None:
    if not auto_platform_auth:
        return
    if _has_explicit_auth_header(headers):
        return
    if not _is_platform_request(url, platform_base_url=platform_base_url):
        return
    token, _source = _resolve_platform_access_token(access_token, auth_loader=auth_loader)
    if not token:
        return
    headers["Authorization"] = f"Bearer {token}"


def _encode_multipart_form_data(field_name: str, file_path: str) -> tuple[bytes, str]:
    path = Path(file_path)
    boundary = f"capafy-{uuid.uuid4().hex}"
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    file_bytes = path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{path.name}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")
    return body, boundary


def _header_value(headers, key: str) -> str:
    if headers is None:
        return ""
    target = key.strip().lower()
    if isinstance(headers, dict):
        for name, value in headers.items():
            if str(name).strip().lower() == target:
                return str(value or "")
        return ""
    getter = getattr(headers, "get", None)
    if getter is None:
        return ""
    value = getter(key)
    if value is None:
        value = getter(key.lower())
    return str(value or "")


def _maybe_log_skill_version_status(headers) -> None:
    status = _header_value(headers, SKILL_VERSION_STATUS_HEADER).strip().lower()
    if status == "outdated":
        print("[http] user skill update available; run `python3 scripts/self_update.py` to upgrade (X-Skill-Version-Status: outdated)", file=sys.stderr)
    elif status == "deprecated":
        print("[http] user skill version is deprecated; upgrade may be required soon", file=sys.stderr)


def _recover_msys_mangled_url(url: str) -> str:
    """Recover an API path that was mangled by MSYS / Cygwin / Git Bash.

    On Windows, passing a relative path like ``/agent/account`` through a
    POSIX-style shell (Git Bash, MSYS, Cygwin) often rewrites the
    argument to a full Windows path such as
    ``C:/Program Files/Git/agent/account`` before the script ever sees
    it. The argument then arrives without an ``http(s)://`` scheme but
    with a drive letter and possibly backslashes, and urllib rejects it
    with "unknown url type: c". Detect that shape and reconstruct the
    original API path so the caller can proceed as if the shell had not
    interfered. No-op when the URL already has a scheme, already starts
    with ``/``, or does not contain an ``/agent/`` or ``/auth/`` segment.
    """
    if "://" in url or url.startswith("/"):
        return url
    normalized = url.replace("\\", "/")
    for segment in ("/agent/", "/auth/"):
        idx = normalized.find(segment)
        if idx != -1:
            recovered = normalized[idx:]
            print(
                f"[http] recovered MSYS-mangled URL {url!r} -> {recovered!r}",
                file=sys.stderr,
            )
            return recovered
    return url


def request(
    method: str,
    url: str,
    json_body: dict | None = None,
    headers: dict[str, str] | None = None,
    out_file: str | None = None,
    *,
    file_field: str | None = None,
    file_path: str | None = None,
    auth_loader=None,
    auto_platform_auth: bool = False,
    access_token: Optional[str] = None,
    platform_base_url: Optional[str] = None,
) -> tuple[dict | str | None, int]:
    url = _recover_msys_mangled_url(url)
    if url.startswith("/"):
        base = _normalize_platform_base_url(platform_base_url)
        if not base:
            raise ValueError(f"relative URL {url!r} requires a platform base URL")
        url = f"{base}{url}"

    all_headers = {"Accept": "application/json"}
    all_headers.update(_normalize_headers(headers))
    _maybe_inject_platform_context_headers(
        url,
        all_headers,
        platform_base_url=platform_base_url,
    )
    _maybe_inject_platform_auth_header(
        url,
        all_headers,
        auto_platform_auth=auto_platform_auth,
        access_token=access_token,
        platform_base_url=platform_base_url,
        auth_loader=auth_loader,
    )

    body_bytes = None
    if file_field and file_path:
        body_bytes, boundary = _encode_multipart_form_data(file_field, file_path)
        all_headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif json_body is not None:
        body_bytes = json.dumps(json_body).encode("utf-8")
        all_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        url,
        data=body_bytes,
        headers=all_headers,
        method=method.upper(),
    )

    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            _maybe_log_skill_version_status(getattr(resp, "headers", None))
            raw = resp.read()
            if out_file:
                Path(out_file).write_bytes(raw)
                return out_file, status
            text = raw.decode(errors="replace")
            try:
                return json.loads(text), status
            except json.JSONDecodeError:
                return text, status
    except urllib.error.HTTPError as exc:
        status = exc.code
        _maybe_log_skill_version_status(getattr(exc, "headers", None))
        raw = exc.read().decode(errors="replace")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = raw
        print(f"[http] {method} {url} -> {status}", file=sys.stderr)
        print(f"[http] response: {body}", file=sys.stderr)
        return body, status
    except urllib.error.URLError as exc:
        print(f"[http] network error: {exc.reason}", file=sys.stderr)
        return None, 0


def _parse_header(text: str) -> tuple[str, str]:
    key, _, value = text.partition(":")
    return key.strip(), value.strip()


def _parse_file_option(text: str) -> tuple[str, str]:
    field, _, path = text.partition("=")
    if not field or not path:
        raise ValueError("--file must use <field>=<path>")
    return field.strip(), path.strip()


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="capafy HTTP tool")
    parser.add_argument("method", choices=["GET", "POST", "PATCH", "DELETE", "PUT"])
    parser.add_argument("url")
    parser.add_argument("--json", dest="json_str")
    parser.add_argument(
        "--json-stdin",
        dest="json_stdin",
        action="store_true",
        help="Read the JSON request body from stdin instead of --json. Use this on Windows PowerShell to avoid native-argv quote stripping.",
    )
    parser.add_argument("--file", dest="file_arg")
    parser.add_argument("--header", action="append", dest="headers", metavar="Key:Value")
    parser.add_argument("--out", dest="out_file")
    parser.add_argument("--access-token", dest="access_token", help="Explicit platform access token for platform-host auto auth")
    parser.add_argument("--no-auto-platform-token", action="store_true", help="Disable platform-host token auto injection")
    parser.add_argument("--no-auth", action="store_true")
    args = parser.parse_args(argv)

    headers: dict[str, str] = {}
    if args.headers:
        for item in args.headers:
            key, value = _parse_header(item)
            headers[key] = value

    json_body = None
    if args.json_stdin:
        if args.json_str:
            parser.error("--json and --json-stdin are mutually exclusive")
        stdin_text = sys.stdin.read()
        if not stdin_text.strip():
            parser.error("--json-stdin set but stdin was empty")
        try:
            json_body = json.loads(stdin_text)
        except json.JSONDecodeError as exc:
            parser.error(f"--json-stdin payload is not valid JSON: {exc}")
    elif args.json_str:
        json_body = json.loads(args.json_str)

    file_field = None
    file_path = None
    if args.file_arg:
        file_field, file_path = _parse_file_option(args.file_arg)

    auth_loader = None if args.no_auth else auth.load_token
    body, status = request(
        args.method,
        args.url,
        json_body=json_body,
        headers=headers,
        out_file=args.out_file,
        file_field=file_field,
        file_path=file_path,
        auth_loader=auth_loader,
        auto_platform_auth=not (args.no_auth or args.no_auto_platform_token),
        access_token=args.access_token,
    )

    if body is None:
        return 1
    if args.out_file:
        print(f"[http] {status} wrote {body}")
    elif isinstance(body, dict):
        print(json.dumps(body, ensure_ascii=False, indent=2))
    else:
        print(body)
    return 0 if status < 400 else 1


if __name__ == "__main__":
    sys.exit(_main())
