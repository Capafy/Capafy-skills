from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any


PLATFORM_ACCESS_TOKEN_ENV = "CAPAFY_ACCESS_TOKEN"
TOKEN_ENV_VAR = "CAPAFY_TOKEN"
TOKEN_STORE_FILENAME = "config.json"


def buyer_skill_dir_path(current_file: Path | None = None) -> Path:
    base = Path(current_file) if current_file is not None else Path(__file__).resolve()
    return base.parents[1]


def token_file_path(home_dir: Path | None = None) -> Path:
    return token_store_path(home_dir)


def token_store_path(home_dir: Path | None = None) -> Path:
    base = Path(home_dir) if home_dir is not None else buyer_skill_dir_path()
    return base / TOKEN_STORE_FILENAME


def _safe_chmod(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except OSError:
        return


def persist_access_token(
    access_token: str,
    *,
    home_dir: Path | None = None,
    user_id: str | None = None,
    email: str | None = None,
    name: str | None = None,
) -> Path:
    normalized_access_token = str(access_token or "").strip()
    if not normalized_access_token:
        raise ValueError("access_token cannot be empty")

    payload = {
        "access_token": normalized_access_token,
        "user_id": str(user_id or "").strip(),
        "email": str(email or "").strip(),
        "name": str(name or "").strip(),
    }
    path = token_store_path(home_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _safe_chmod(path, 0o600)
    return path


def save_token(
    token: str,
    home_dir: Path | None = None,
    *,
    user_id: str | None = None,
    email: str | None = None,
    name: str | None = None,
) -> Path:
    return persist_access_token(
        token,
        home_dir=home_dir,
        user_id=user_id,
        email=email,
        name=name,
    )


def load_persisted_token_payload(home_dir: Path | None = None) -> dict[str, Any] | None:
    path = token_store_path(home_dir)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid token store json: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"token store must be a JSON object: {path}")
    return payload


def load_persisted_access_token(home_dir: Path | None = None) -> tuple[str, Path] | None:
    payload = load_persisted_token_payload(home_dir)
    if payload is None:
        return None
    access_token = str(payload.get("access_token", "")).strip()
    path = token_store_path(home_dir)
    if not access_token:
        raise ValueError(f"token store missing access_token: {path}")
    return access_token, path


def load_token(home_dir: Path | None = None) -> str | None:
    platform_env_value = os.environ.get(PLATFORM_ACCESS_TOKEN_ENV, "").strip()
    if platform_env_value:
        return platform_env_value

    env_value = os.environ.get(TOKEN_ENV_VAR, "").strip()
    if env_value:
        return env_value

    persisted = load_persisted_access_token(home_dir)
    if persisted is None:
        return None
    value, _path = persisted
    return value or None


def clear_token(home_dir: Path | None = None) -> None:
    path = token_store_path(home_dir)
    if path.exists():
        path.unlink()


def has_token(home_dir: Path | None = None) -> bool:
    try:
        return load_token(home_dir) is not None
    except ValueError:
        return False


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="User Skill token storage helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    save_parser = subparsers.add_parser("save")
    save_parser.add_argument("token")

    subparsers.add_parser("load")
    subparsers.add_parser("clear")
    subparsers.add_parser("check")

    try:
        args = parser.parse_args(argv)
        if args.command == "save":
            path = save_token(args.token)
            print(path)
            return 0
        if args.command == "load":
            token = load_token()
            if token is None:
                return 1
            print(token)
            return 0
        if args.command == "clear":
            clear_token()
            return 0
        if args.command == "check":
            print("configured" if has_token() else "missing")
            return 0 if has_token() else 1
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(_main())
