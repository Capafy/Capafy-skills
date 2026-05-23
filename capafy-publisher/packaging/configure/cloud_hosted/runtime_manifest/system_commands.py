from __future__ import annotations

import subprocess


def run_text_command(args: list[str], timeout: int = 10) -> dict:
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {
            "ok": False,
            "error": type(exc).__name__,
        }

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    payload = {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
    }
    if stdout:
        payload["stdout"] = stdout
    if stderr:
        payload["stderr"] = stderr
    return payload


__all__ = ["run_text_command"]
