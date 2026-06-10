from __future__ import annotations

import json


def invalid_json_config_error(label: str, relpath: str, exc: json.JSONDecodeError) -> ValueError:
    return ValueError(
        f"invalid {label} JSON at {relpath}: "
        f"{exc.msg} (line {exc.lineno}, column {exc.colno})"
    )


def invalid_text_config_error(label: str, format_name: str, relpath: str, detail: str = "") -> ValueError:
    suffix = f": {detail}" if detail else ""
    return ValueError(f"invalid {label} {format_name} at {relpath}{suffix}")


__all__ = ["invalid_json_config_error", "invalid_text_config_error"]
