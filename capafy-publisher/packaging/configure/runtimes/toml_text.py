from __future__ import annotations

import json
import re



SECTION_PATTERN = re.compile(r"^\s*\[([^\]]+)\]\s*$")




KEY_VALUE_PATTERN = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_-]*)(\s*=\s*)(.*?)(\s*)$")


BARE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def newline_for(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


__all__ = [
    "BARE_KEY_PATTERN",
    "KEY_VALUE_PATTERN",
    "SECTION_PATTERN",
    "newline_for",
    "toml_string",
]
