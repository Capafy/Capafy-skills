#!/usr/bin/env python3


from __future__ import annotations
from typing import Optional

import argparse
import sys
from pathlib import Path

from packaging._shared.common.cli import emit_json_result, fail
from packaging.init.publish_init import publish_init
from packaging.configure.publish_configure import publish_configure
from packaging.ship.publish_ship import publish_ship
from packaging.ship.status import publish_status
from capafy_platform.login_commands import (
    command_platform_login_init,
    command_platform_login_token,
    command_platform_login_verify,
)

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publisher skill packaging helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    login_init_parser = subparsers.add_parser("login-init")
    login_init_parser.add_argument("--email", required=True)
    login_init_parser.add_argument("--base-url")

    login_verify_parser = subparsers.add_parser("login-verify")
    login_verify_parser.add_argument("--challenge-id", required=True)
    login_verify_parser.add_argument("--code", required=True)
    login_verify_parser.add_argument("--base-url")

    login_token_parser = subparsers.add_parser("login-token")
    login_token_parser.add_argument("--access-token", required=True)
    login_token_parser.add_argument("--base-url")

    publish_init_parser = subparsers.add_parser("publish-init")
    publish_init_parser.add_argument("--env", required=True)
    publish_init_parser.add_argument("--runtime-dir", required=True)
    publish_init_parser.add_argument("--skill-dir")
    publish_init_parser.add_argument("--agent-id")
    selections_group = publish_init_parser.add_mutually_exclusive_group()
    selections_group.add_argument("--selections")
    selections_group.add_argument("--selections-file")
    publish_init_parser.add_argument("--reset-local-state", action="store_true")

    publish_configure_parser = subparsers.add_parser("publish-configure")
    publish_configure_parser.add_argument("--agent-id", required=True)
    publish_configure_parser.add_argument("--dispositions-file")
    publish_configure_parser.add_argument("--deep-scan", action="store_true")
    publish_configure_parser.add_argument("--deep-scan-findings-file")

    ship_parser = subparsers.add_parser("publish-ship")
    ship_parser.add_argument("--agent-id", required=True)

    subparsers.add_parser("publish-status")

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]

    args = _build_parser().parse_args(raw_argv)
    try:
        if args.command == "login-init":
            return command_platform_login_init(
                args.email,
                base_url=args.base_url,
            )
        if args.command == "login-verify":
            return command_platform_login_verify(
                args.challenge_id,
                args.code,
                base_url=args.base_url,
            )
        if args.command == "login-token":
            return command_platform_login_token(
                args.access_token,
                base_url=args.base_url,
            )

        if args.command == "publish-init":
            selections_json = args.selections
            if args.selections_file:
                selections_json = Path(args.selections_file).read_text(encoding="utf-8")
            return publish_init(
                env_id=args.env,
                runtime_dir=args.runtime_dir,
                skill_dir=args.skill_dir,
                agent_id=args.agent_id,
                selections_json=selections_json,
                reset_local_state=args.reset_local_state,
            )
        if args.command == "publish-configure":
            return publish_configure(
                agent_id=args.agent_id,
                dispositions_file=args.dispositions_file,
                deep_scan=args.deep_scan,
                deep_scan_findings_file=args.deep_scan_findings_file,
            )
        if args.command == "publish-ship":
            return publish_ship(agent_id=args.agent_id)
        if args.command == "publish-status":
            return publish_status()
    except Exception as exc:  # pragma: no cover - CLI safety
        return emit_json_result({"status": "error", "error": str(exc)}, 1)

    return fail(f"Unknown command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
