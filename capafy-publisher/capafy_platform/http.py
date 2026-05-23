from __future__ import annotations

import json
import os
import sys
from typing import Any
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from capafy_platform.defaults import DEFAULT_HTTP_TIMEOUT_SECONDS, DEFAULT_PLATFORM_BASE_URL
from capafy_platform import runtime_context
from capafy_platform.token_store import load_persisted_access_token

PLATFORM_BASE_URL_ENV = "CAPAFY_PLATFORM_BASE_URL"
PLATFORM_ACCESS_TOKEN_ENV = "CAPAFY_ACCESS_TOKEN"
EXPLICIT_AUTH_HEADER_KEYS = {"authorization", "x-access-token"}
SKILL_VERSION_STATUS_HEADER = "X-Skill-Version-Status"
_LAST_SKILL_VERSION_STATUS: str | None = None


def platform_context_headers() -> dict[str, str]:
    return runtime_context.platform_context_headers()


def _maybe_inject_platform_context_headers(
    url: str,
    headers: dict[str, Any],
    *,
    platform_base_url: str | None = None,
) -> None:
    if not _is_platform_request(url, platform_base_url=platform_base_url):
        return
    for key, value in runtime_context.platform_context_headers().items():
        headers.setdefault(key, value)


def _origin_parts(url: str) -> tuple[str, str, int]:
    parsed = urlsplit(url)
    host = str(parsed.hostname or "").lower().strip()
    scheme = str(parsed.scheme or "").lower()
    port = parsed.port
    if port is None:
        port = 443 if scheme == "https" else 80
    return scheme, host, port


def _is_platform_request(url: str, *, platform_base_url: str | None = None) -> bool:
    try:
        normalized_base_url = normalize_platform_base_url(platform_base_url)
    except ValueError:
        return False
    return _origin_parts(url) == _origin_parts(normalized_base_url)


def _has_explicit_auth_header(headers: dict[str, Any]) -> bool:
    return any(str(key).strip().lower() in EXPLICIT_AUTH_HEADER_KEYS for key in headers)


def _resolve_platform_access_token(access_token: str | None = None) -> str | None:
    explicit_token = str(access_token or "").strip()
    if explicit_token:
        return explicit_token

    env_token = str(os.environ.get(PLATFORM_ACCESS_TOKEN_ENV, "")).strip()
    if env_token:
        return env_token

    try:
        persisted = load_persisted_access_token()
    except ValueError as exc:
        print(f"[http] failed to load local platform token: {exc}", file=sys.stderr)
        return None
    if persisted is None:
        return None
    persisted_token, _path = persisted
    return persisted_token


def _maybe_inject_platform_auth_header(
    url: str,
    headers: dict[str, Any],
    *,
    auto_platform_auth: bool = False,
    access_token: str | None = None,
    platform_base_url: str | None = None,
) -> None:
    if not auto_platform_auth:
        return
    if _has_explicit_auth_header(headers):
        return
    if not _is_platform_request(url, platform_base_url=platform_base_url):
        return
    token = _resolve_platform_access_token(access_token)
    if not token:
        return
    headers["Authorization"] = f"Bearer {token}"


def get_last_skill_version_status() -> str | None:
    return _LAST_SKILL_VERSION_STATUS


def _maybe_log_skill_version_status(headers: Any) -> None:
    global _LAST_SKILL_VERSION_STATUS
    try:
        raw = headers.get(SKILL_VERSION_STATUS_HEADER, "").strip().lower()
    except (AttributeError, TypeError):
        _LAST_SKILL_VERSION_STATUS = None
        return
    _LAST_SKILL_VERSION_STATUS = raw or None
    if raw == "outdated":
        print(
            "[http] publisher skill update available; run self_update.py to upgrade "
            "(X-Skill-Version-Status: outdated)",
            file=sys.stderr,
        )
    elif raw == "deprecated":
        print("[http] publisher skill version is deprecated; upgrade may be required soon", file=sys.stderr)


def request(
    method: str,
    url: str,
    json_body: dict[str, Any] | None = None,
    headers: dict[str, Any] | None = None,
    out_file: str | None = None,
    *,
    auto_platform_auth: bool = False,
    access_token: str | None = None,
    platform_base_url: str | None = None,
    timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
) -> tuple[Any, int]:
    global _LAST_SKILL_VERSION_STATUS
    _LAST_SKILL_VERSION_STATUS = None

    all_headers: dict[str, Any] = {"Accept": "application/json"}
    if headers:
        all_headers.update(headers)
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
    )

    body_bytes = None
    if json_body is not None:
        body_bytes = json.dumps(json_body).encode()
        all_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        url,
        data=body_bytes,
        headers=all_headers,
        method=method.upper(),
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            status = resp.status
            raw = resp.read()
            _maybe_log_skill_version_status(getattr(resp, "headers", None))

            if out_file:
                with open(out_file, "wb") as handle:
                    handle.write(raw)
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
        print(f"[http] {method} {url} → {status}", file=sys.stderr)
        print(f"[http] response: {body}", file=sys.stderr)
        return body, status
    except urllib.error.URLError as exc:
        print(f"[http] network error: {exc.reason}", file=sys.stderr)
        return None, 0


def normalize_platform_base_url(base_url: str | None) -> str:
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


def build_platform_auth_headers(access_token: str | None = None) -> dict[str, str]:
    token = str(_resolve_platform_access_token(access_token) or "").strip()
    if not token:
        raise ValueError("access_token must not be empty")
    return {"Authorization": f"Bearer {token}"}


def _attach_skill_version_status(payload: Any) -> Any:
    warning = str(get_last_skill_version_status() or "").strip().lower()
    if not warning or not isinstance(payload, dict):
        return payload
    if "skill_version_status" in payload and str(payload.get("skill_version_status") or "").strip():
        return payload
    enriched = dict(payload)
    enriched["skill_version_status"] = warning
    return enriched


def unwrap_platform_response(path: str, body: Any, *, allow_raw_dict_without_code: bool = False) -> dict:
    if not isinstance(body, dict):
        raise ValueError(f"{path} response is not a JSON object")
    if "code" not in body:
        if allow_raw_dict_without_code:
            return body
        raise ValueError(f"{path} response is missing standard platform code")
    code = body.get("code")
    if code not in (0, "0", None):
        raise ValueError(f"{path} platform returned an error: {body.get('msg') or body}")
    data = body.get("data", {})
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} response data must be an object")
    return data


def _request_platform_json(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    base_url: str | None = None,
    access_token: str | None = None,
    require_auth: bool = False,
    unauthorized_message: str | None = None,
    allow_raw_dict_without_code: bool = False,
) -> dict:
    headers = None
    if require_auth:
        headers = build_platform_auth_headers(access_token)
    url = f"{normalize_platform_base_url(base_url)}{path}"
    request_kwargs: dict[str, Any] = {}
    if base_url is not None:
        request_kwargs["platform_base_url"] = base_url
    body, status = request(
        method,
        url,
        json_body=payload,
        headers=headers,
        **request_kwargs,
    )
    if status == 0:
        raise ValueError(f"{path} request failed: network error")
    if status == 401 and unauthorized_message:
        raise ValueError(unauthorized_message)
    if status >= 400:
        raise ValueError(f"{path} request failed: HTTP {status}")
    return _attach_skill_version_status(
        unwrap_platform_response(path, body, allow_raw_dict_without_code=allow_raw_dict_without_code)
    )


def post_platform_json(
    path: str,
    payload: dict[str, Any],
    *,
    base_url: str | None = None,
    access_token: str | None = None,
    require_auth: bool = False,
    unauthorized_message: str | None = None,
) -> dict:
    return _request_platform_json(
        "POST",
        path,
        payload=payload,
        base_url=base_url,
        access_token=access_token,
        require_auth=require_auth,
        unauthorized_message=unauthorized_message,
    )


def get_platform_json(
    path: str,
    *,
    base_url: str | None = None,
    access_token: str | None = None,
    require_auth: bool = False,
    unauthorized_message: str | None = None,
    allow_raw_dict_without_code: bool = False,
) -> dict:
    return _request_platform_json(
        "GET",
        path,
        base_url=base_url,
        access_token=access_token,
        require_auth=require_auth,
        unauthorized_message=unauthorized_message,
        allow_raw_dict_without_code=allow_raw_dict_without_code,
    )


__all__ = [
    "get_last_skill_version_status",
    "get_platform_json",
    "normalize_platform_base_url",
    "post_platform_json",
    "request",
]
