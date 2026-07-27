from __future__ import annotations

import json
import re
from pathlib import Path

from packaging._shared.common.fs import path_basename
from packaging._shared.common.local_path_detection import (
    LOCAL_HOST_PATTERN,
    LOCAL_PATH_PATTERN,
    LOCAL_PATH_PLACEHOLDER,
    redact_local_traces_in_text,
)


def _in_cli_backends_subtree(path_parts: list[str]) -> bool:
    lowered = [part.lower() for part in path_parts]
    try:
        agents_index = lowered.index("agents")
        cli_backends_index = lowered.index("clibackends", agents_index + 1)
    except ValueError:
        return False
    return cli_backends_index > agents_index


def _value_has_local_trace(value: str) -> bool:
    stripped = str(value or "").strip()
    if not stripped:
        return False
    return bool(LOCAL_HOST_PATTERN.search(stripped) or LOCAL_PATH_PATTERN.search(stripped))


def _rewrite_cli_command(value: str) -> str:
    match = re.match(r'^(?P<head>"[^"]+"|\'[^\']+\'|\S+)(?P<tail>.*)$', value.strip())
    if not match:
        return LOCAL_PATH_PLACEHOLDER
    head = match.group("head")
    tail = match.group("tail")
    quote = head[0] if len(head) >= 2 and head[0] == head[-1] and head[0] in {'"', "'"} else ""
    raw_head = head[1:-1] if quote else head

    if LOCAL_HOST_PATTERN.search(raw_head):
        rewritten_head = LOCAL_PATH_PLACEHOLDER
    elif LOCAL_PATH_PATTERN.search(raw_head):
        basename = path_basename(raw_head.rstrip("/\\"))
        if not basename:
            rewritten_head = LOCAL_PATH_PLACEHOLDER
        else:
            rewritten_head = f"{quote}{basename}{quote}" if quote else basename
    else:
        rewritten_head = head

    if tail:
        rewritten_tail, _ = redact_local_traces_in_text(tail, replacement=LOCAL_PATH_PLACEHOLDER)
    else:
        rewritten_tail = tail

    return f"{rewritten_head}{rewritten_tail}"


def redact_openclaw_local_configs(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return 0

    redactions = 0

    def walk(node: object, path_parts: list[str]) -> None:
        nonlocal redactions
        if isinstance(node, dict):
            for key, value in node.items():
                key_name = str(key)
                if isinstance(value, str):
                    if _in_cli_backends_subtree(path_parts) and _value_has_local_trace(value):
                        rewritten = _rewrite_cli_command(value) if key_name == "command" else LOCAL_PATH_PLACEHOLDER
                        if rewritten != value:
                            node[key] = rewritten
                            redactions += 1
                            continue
                walk(value, path_parts + [key_name])
            return
        if isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, path_parts + [str(index)])

    gateway = payload.get("gateway")
    if isinstance(gateway, dict):
        tailscale = gateway.get("tailscale")
        if isinstance(tailscale, dict):
            if tailscale.get("mode") != "off":
                tailscale["mode"] = "off"
                redactions += 1
            if tailscale.get("resetOnExit") is not False:
                tailscale["resetOnExit"] = False
                redactions += 1

    walk(payload, [])
    if redactions:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return redactions


__all__ = ["redact_openclaw_local_configs"]
