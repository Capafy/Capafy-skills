from __future__ import annotations

import re
from pathlib import Path

from packaging._shared.common.constants import STRUCTURED_ASSIGNMENT_PATTERNS
from packaging._shared.common.local_path_detection import LOCAL_PATH_PLACEHOLDER, looks_like_local_path
from packaging._shared.policies.path_refs import is_packaged_runtime_ref
from packaging.configure.sensitive.keywords import normalize_key_name
from packaging.configure.sensitive.redact_helpers import split_raw_line, stable_local_placeholder
from packaging.configure.sensitive.redact_constants import RUNTIME_LLM_CONFIG_KEYS


SECTION_PATH_PATTERN = re.compile(r'(?P<prefix>\.(?P<quote>["\']))(?P<value>.*?)(?P=quote)')
QUOTED_LITERAL_PATTERN = re.compile(r'(?P<quote>["\'])(?P<value>.*?)(?P=quote)')

def _is_runtime_llm_config_key(key: str) -> bool:
    return normalize_key_name(key) in RUNTIME_LLM_CONFIG_KEYS


def redact_toml_stage_config(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    redactions = 0
    updated_lines: list[str] = []
    for raw_line in text.splitlines(keepends=True):
        line, newline = split_raw_line(raw_line)
        if line.lstrip().startswith("["):
            def replace_section_path(match: re.Match[str]) -> str:
                nonlocal redactions
                value = match.group("value")
                if not looks_like_local_path(value):
                    return match.group(0)
                redactions += 1
                return f'{match.group("prefix")}{stable_local_placeholder(value)}{match.group("quote")}'

            updated_lines.append(SECTION_PATH_PATTERN.sub(replace_section_path, line) + newline)
            continue

        assignment = STRUCTURED_ASSIGNMENT_PATTERNS[0].match(line)
        if assignment and _is_runtime_llm_config_key(assignment.group("key")):
            updated_lines.append(line + newline)
            continue

        def replace_literal(match: re.Match[str]) -> str:
            nonlocal redactions
            value = match.group("value")
            if is_packaged_runtime_ref(value):
                return match.group(0)
            if not looks_like_local_path(value):
                return match.group(0)
            redactions += 1
            return f'{match.group("quote")}{LOCAL_PATH_PLACEHOLDER}{match.group("quote")}'

        updated_lines.append(QUOTED_LITERAL_PATTERN.sub(replace_literal, line) + newline)

    if redactions:
        path.write_text("".join(updated_lines), encoding="utf-8")
    return redactions


__all__ = [
    "redact_toml_stage_config",
]
