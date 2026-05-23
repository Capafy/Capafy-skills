from __future__ import annotations

import re
from pathlib import Path

from packaging._shared.common.constants import STRUCTURED_ASSIGNMENT_PATTERNS
from packaging._shared.common.local_path_detection import LOCAL_PATH_PLACEHOLDER, looks_like_local_path
from packaging._shared.policies.path_refs import is_packaged_runtime_ref
from packaging.configure.sensitive.keywords import normalize_key_name


SECTION_PATH_PATTERN = re.compile(r'^(\s*\[projects\.(["\']))(.+?)(\2\]\s*)$')
QUOTED_LITERAL_PATTERN = re.compile(r'(?P<quote>["\'])(?P<value>.*?)(?P=quote)')

_RUNTIME_LLM_CONFIG_KEYS = {
    "apikey",
    "apikeys",
    "apiurl",
    "baseurl",
    "envkey",
    "openaikey",
    "openaiapikey",
    "openaibaseurl",
    "anthropicapikey",
    "anthropicauthtoken",
    "anthropicbaseurl",
    "authorization",
}


def _is_runtime_llm_config_key(key: str) -> bool:
    return normalize_key_name(key) in _RUNTIME_LLM_CONFIG_KEYS


def _redact_toml_line(line: str, *, source: str, line_no: int) -> tuple[str, int]:
    from packaging.configure.sensitive.config_redact import _replace_assignment_value
    from packaging.configure.sensitive.config_redact import _stable_local_placeholder

    redactions = 0
    match = SECTION_PATH_PATTERN.match(line)
    if match and looks_like_local_path(match.group(3)):
        placeholder = _stable_local_placeholder(match.group(3))
        return f"{match.group(1)}{placeholder}{match.group(4)}", 1

    replaced, count = _replace_assignment_value(
        line,
        pattern=STRUCTURED_ASSIGNMENT_PATTERNS[0],
        source=source,
        source_detail=f"line {line_no}",
    )
    if count:
        return replaced, count

    def replace_literal(match: re.Match[str]) -> str:
        nonlocal redactions
        value = match.group("value")
        if is_packaged_runtime_ref(value):
            return match.group(0)
        if not looks_like_local_path(value):
            return match.group(0)
        redactions += 1
        return f'{match.group("quote")}{LOCAL_PATH_PLACEHOLDER}{match.group("quote")}'

    replaced = QUOTED_LITERAL_PATTERN.sub(replace_literal, line)
    return replaced, redactions


def redact_toml_local_config(path: Path, source: str | None = None) -> int:
    from packaging.configure.sensitive.config_redact import _split_raw_line

    text = path.read_text(encoding="utf-8")
    redactions = 0
    updated_lines: list[str] = []
    relative_source = source or path.name
    for line_no, raw_line in enumerate(text.splitlines(keepends=True), start=1):
        line, newline = _split_raw_line(raw_line)
        replaced, count = _redact_toml_line(line, source=relative_source, line_no=line_no)
        redactions += count
        updated_lines.append(replaced + newline)

    if redactions:
        path.write_text("".join(updated_lines), encoding="utf-8")
    return redactions


def redact_toml_stage_config(path: Path) -> int:
    from packaging.configure.sensitive.config_redact import _split_raw_line
    from packaging.configure.sensitive.config_redact import _stable_local_placeholder

    text = path.read_text(encoding="utf-8")
    redactions = 0
    updated_lines: list[str] = []
    for raw_line in text.splitlines(keepends=True):
        line, newline = _split_raw_line(raw_line)
        match = SECTION_PATH_PATTERN.match(line)
        if match and looks_like_local_path(match.group(3)):
            placeholder = _stable_local_placeholder(match.group(3))
            updated_lines.append(f"{match.group(1)}{placeholder}{match.group(4)}{newline}")
            redactions += 1
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
    "redact_toml_local_config",
    "redact_toml_stage_config",
]
