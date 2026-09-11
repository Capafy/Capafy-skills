#!/usr/bin/env python3


from __future__ import annotations
from typing import Optional

import argparse
import json
import os
import sys
from pathlib import Path

from self_update_v2 import check_min_supported_version, self_update


def _ensure_local_packaging_not_shadowed() -> None:
    loaded = sys.modules.get("packaging")
    if loaded is None:
        return
    loaded_file = Path(str(getattr(loaded, "__file__", "") or "")).resolve()
    expected_dir = (Path(__file__).resolve().parent / "packaging").resolve()
    if loaded_file.parent != expected_dir:
        raise RuntimeError(
            "Python module name conflict: PyPI 'packaging' was imported before "
            "capafy-publisher's local packaging package. Run packager.py as a script "
            "from the capafy-publisher directory, or start a fresh Python process with "
            "this skill directory first on PYTHONPATH."
        )


_ensure_local_packaging_not_shadowed()

from packaging.common.cli import fail
from packaging.publish.init.command import publish_init
from packaging.publish.submit.command import PUBLISH_SUBMIT_ACTIONS, publish_submit
from packaging.publish.platform.remote_status import publish_list, publish_remote_status
from packaging.publish.platform.remote_status import publish_refresh_url
from packaging.publish.platform.status import publish_status
from capafy_platform.login_commands import (
    command_platform_login_init,
    command_platform_login_token,
    command_platform_login_verify,
)

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publisher skill packaging helper",
        allow_abbrev=False,
    )
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

    publish_init_parser = subparsers.add_parser("publish-init", allow_abbrev=False)
    publish_init_parser.add_argument("--env", required=True)
    publish_init_parser.add_argument("--runtime-dir", required=True)
    publish_init_parser.add_argument("--skill-dir")
    publish_init_parser.add_argument("--agent-id")
    publish_init_parser.add_argument("--brief", action="store_true")
    publish_init_parser.add_argument("--title")
    publish_init_parser.add_argument("--description")
    publish_init_parser.add_argument("--selections-file")
    publish_init_parser.add_argument("--reset-local-state", action="store_true")

    publish_submit_parser = subparsers.add_parser("publish-submit")
    publish_submit_parser.add_argument("--agent-id", required=True)
    publish_submit_parser.add_argument(
        "--action",
        choices=PUBLISH_SUBMIT_ACTIONS,
        required=True,
    )
    publish_submit_parser.add_argument("--dispositions-file")
    publish_submit_parser.add_argument("--deep-scan", action="store_true")
    publish_submit_parser.add_argument("--deep-scan-findings-file")
    publish_submit_parser.add_argument("--environment-selection-file")

    remote_status_parser = subparsers.add_parser("publish-remote-status")
    remote_status_parser.add_argument("--agent-id", required=True)

    refresh_url_parser = subparsers.add_parser("publish-refresh-url")
    refresh_url_parser.add_argument("--agent-id", required=True)
    refresh_url_parser.add_argument("--step", choices=("init", "publish"))

    subparsers.add_parser("publish-list")

    subparsers.add_parser("publish-status")

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]

    args = _build_parser().parse_args(raw_argv)
    version_check = None
    try:
        version_check = check_min_supported_version(
            Path(__file__).resolve().parent,
            base_url=getattr(args, "base_url", None),
        )
        if version_check["update_required"]:
            update_result = self_update(
                skill_dir=Path(__file__).resolve().parent,
                base_url=getattr(args, "base_url", None),
            )
            if update_result.get("status") == "updated":
                os.execv(
                    sys.executable,
                    [sys.executable, str(Path(__file__).resolve()), *raw_argv],
                )
            print(json.dumps({
                "status": "restart_required",
                **version_check,
                "update": update_result,
                "message": "Publisher Skill was updated, but locked files are pending; restart the host before retrying.",
                "next_step": "restart the host, then retry the same command",
            }, ensure_ascii=False), file=sys.stderr)
            return 1
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
            selections_json = None
            if args.selections_file:
                selections_json = Path(args.selections_file).read_text(encoding="utf-8")
            return publish_init(
                env_id=args.env,
                runtime_dir=args.runtime_dir,
                skill_dir=args.skill_dir,
                agent_id=args.agent_id,
                selections_json=selections_json,
                reset_local_state=args.reset_local_state,
                brief=args.brief,
                title=args.title,
                description=args.description,
            )
        if args.command == "publish-submit":
            return publish_submit(
                agent_id=args.agent_id,
                action=args.action,
                dispositions_file=args.dispositions_file,
                deep_scan=args.deep_scan,
                deep_scan_findings_file=args.deep_scan_findings_file,
                environment_selection_file=args.environment_selection_file,
            )
        if args.command == "publish-remote-status":
            return publish_remote_status(agent_id=args.agent_id)
        if args.command == "publish-refresh-url":
            return publish_refresh_url(agent_id=args.agent_id, step=args.step)
        if args.command == "publish-list":
            return publish_list()
        if args.command == "publish-status":
            return publish_status()
    except Exception as exc:  # pragma: no cover - CLI safety
        return fail(str(exc))
    finally:
        if version_check and version_check.get("update_available") and not version_check.get("update_required"):
            print(
                "Publisher Skill update available (local version "
                f"{version_check.get('local_version')}, latest version {version_check.get('latest_version')}). "
                "Run self-update V2 when convenient.",
                file=sys.stderr,
            )

    return fail(f"Unknown command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
