from __future__ import annotations

from typing import Any

from capafy_platform.http import post_platform_json


def build_login_init_request(email: str) -> dict[str, str]:
    normalized_email = str(email or "").strip()
    if not normalized_email:
        raise ValueError("email must not be empty")
    return {
        "loginMethod": "email",
        "email": normalized_email,
    }


def build_login_verify_request(
    challenge_id: str,
    code: str,
) -> dict[str, str]:
    normalized_challenge_id = str(challenge_id or "").strip()
    if not normalized_challenge_id:
        raise ValueError("challenge_id must not be empty")
    normalized_code = str(code or "").strip()
    if not normalized_code:
        raise ValueError("code must not be empty")
    return {
        "challengeId": normalized_challenge_id,
        "code": normalized_code,
        "source": "agent",
    }



def login_init(email: str, *, base_url: str | None = None) -> dict[str, Any]:
    request_body = build_login_init_request(email)
    data = post_platform_json("/auth/login", request_body, base_url=base_url)
    response = {
        "api_action": "login_init",
        "request_body": request_body,
        "challenge_id": str(data.get("challengeId", "")).strip(),
        "expires_in_sec": data.get("expiresInSec"),
        "raw_data": data,
    }
    warning = str(data.get("skill_version_status", "")).strip().lower()
    if warning:
        response["skill_version_status"] = warning
    return response


def login_verify(
    challenge_id: str,
    code: str,
    base_url: str | None = None,
) -> dict[str, Any]:
    request_body = build_login_verify_request(challenge_id, code)
    data = post_platform_json("/auth/login/verify", request_body, base_url=base_url)
    response = {
        "api_action": "login_verify",
        "request_body": request_body,
        "source": request_body["source"],
        "user_id": str(data.get("userId", "")).strip(),
        "email": str(data.get("email", "")).strip(),
        "name": str(data.get("name", "")).strip(),
        "access_token": str(data.get("accessToken", "")).strip(),
        "raw_data": data,
    }
    warning = str(data.get("skill_version_status", "")).strip().lower()
    if warning:
        response["skill_version_status"] = warning
    return response




__all__ = [
    "build_login_init_request",
    "build_login_verify_request",
    "login_init",
    "login_verify",
]
