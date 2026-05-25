from __future__ import annotations
from typing import Optional

import re
from pathlib import PurePosixPath

from packaging.configure.sensitive.literals import looks_like_placeholder_value


NON_RUNTIME_PATH_PARTS = {
    ".research",
    "archive",
    "doc",
    "docs",
    "example",
    "examples",
    "fixture",
    "fixtures",
    "full_archive",
    "reference",
    "references",
    "sample",
    "samples",
    "test",
    "tests",
}

TEMPLATE_BASENAMES = {
    ".env.example",
    ".env.sample",
    ".env.template",
}

TEMPLATE_NAME_MARKERS = (
    ".example.",
    ".sample.",
    ".template.",
    "-example.",
    "-sample.",
    "-template.",
    "_example.",
    "_sample.",
    "_template.",
)

NON_RUNTIME_METADATA_BASENAMES = {
    "marketplace.json",
    "plugin.json",
}

PUBLIC_CLIENT_WEB_KEY_MARKERS = (
    "placesapikey",
    "mapsapikey",
    "recaptchav3sitekey",
    "googleanalyticsaccount",
    "gtmkey",
    "google-site-verification",
    "facebookappid",
    "fb:app_id",
)

SAMPLE_SECRET_MARKERS = (
    "xxxx",
    "123456",
    "abcdef",
    "example",
    "sample",
    "placeholder",
    "changeme",
    "replace_me",
)

REPEATED_SAMPLE_CHARS_PATTERN = re.compile(r"(?:^|[_-])([a-z0-9])\1{5,}$", re.IGNORECASE)


def _looks_like_sample_secret_value(value: str) -> bool:
    lowered = value.strip().lower()
    if not lowered:
        return False
    if looks_like_placeholder_value(lowered):
        return True
    if any(marker in lowered for marker in SAMPLE_SECRET_MARKERS):
        return True
    if REPEATED_SAMPLE_CHARS_PATTERN.search(lowered):
        return True
    return False


def _should_drop_candidate(relpath: str, candidate: dict, line: Optional[str] = None) -> bool:
    pure = PurePosixPath(relpath)
    basename = pure.name.lower()
    path_parts = {part.lower() for part in pure.parts}
    in_non_runtime_path = bool(path_parts & NON_RUNTIME_PATH_PARTS)
    is_template_file = basename in TEMPLATE_BASENAMES or any(marker in basename for marker in TEMPLATE_NAME_MARKERS)
    entry_type = str(candidate.get("entry_type", "api_key"))
    value_type = str(candidate.get("value_type") or "")
    value = str(candidate.get("value", "")).strip()

    if entry_type == "managed_value":
        if is_template_file:
            return True
        if in_non_runtime_path and basename in NON_RUNTIME_METADATA_BASENAMES and value_type == "login_identifier":
            return True
        return False

    lowered_line = (line or "").lower()
    if (
        in_non_runtime_path
        and pure.suffix.lower() in {".html", ".htm"}
        and str(candidate.get("service", "")).strip() == "Google"
        and any(marker in lowered_line for marker in PUBLIC_CLIENT_WEB_KEY_MARKERS)
    ):
        return True

    if in_non_runtime_path and _looks_like_sample_secret_value(value):
        return True
    if is_template_file and _looks_like_sample_secret_value(value):
        return True
    return False


def _is_identifier_char(char: str) -> bool:
    return char.isalnum() or char in {"_", "-", ".", "/"}


def _match_is_embedded_in_identifier(line: str, start_col: int, end_col: int) -> bool:
    before = line[start_col - 1] if start_col > 0 else ""
    after = line[end_col] if end_col < len(line) else ""
    return bool(before and _is_identifier_char(before) or after and _is_identifier_char(after))


def annotate_candidate(
    candidate: dict,
    relpath: str,
    *,
    line: Optional[str] = None,
    match_start_col: Optional[int] = None,
    match_end_col: Optional[int] = None,
) -> Optional[dict]:
    if (
        line is not None
        and match_start_col is not None
        and match_end_col is not None
        and _match_is_embedded_in_identifier(line, match_start_col, match_end_col)
    ):
        return None

    if _should_drop_candidate(relpath, candidate, line=line):
        return None

    return candidate


__all__ = [
    "NON_RUNTIME_PATH_PARTS",
    "NON_RUNTIME_METADATA_BASENAMES",
    "PUBLIC_CLIENT_WEB_KEY_MARKERS",
    "REPEATED_SAMPLE_CHARS_PATTERN",
    "SAMPLE_SECRET_MARKERS",
    "TEMPLATE_BASENAMES",
    "TEMPLATE_NAME_MARKERS",
    "annotate_candidate",
]
