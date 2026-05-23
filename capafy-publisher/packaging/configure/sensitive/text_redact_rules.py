from __future__ import annotations

import re

from packaging._shared.common.constants import SSH_PUBLIC_KEY_PATTERN


SPECIAL_CLEAN_FILENAMES = {"MEMORY.md", "TOOLS.md", "USER.md", "HEARTBEAT.md"}
SPECIAL_CLEAN_RELATIVE_FILES = {
    ".openclaw/workspace/AGENTS.md",
    ".openclaw/workspace/SOUL.md",
}

TOOLS_PATTERNS = [
    re.compile(r"192\.168\.\d+\.\d+"),
    re.compile(r"10\.\d+\.\d+\.\d+"),
    re.compile(r"172\.(1[6-9]|2\d|3[01])\.\d+\.\d+"),
    re.compile(r"127\.0\.0\.1"),

    re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/](?:[^\r\n]+[\\/])*[^\r\n]*"),
    re.compile(r"/home/[^\s/]+"),
    re.compile(r"/Users/[^\s/]+"),
    re.compile(r"\\\\[^\\/\r\n]+\\[^\\\r\n]+(?:\\[^\\\r\n]+)*"),
    re.compile(r"\b[a-zA-Z0-9_.-]+@[a-zA-Z0-9_.-]+\b"),
    SSH_PUBLIC_KEY_PATTERN,
]


USER_FIELD_NAMES = (
    "name",
    "full name",
    "nickname",
    "display name",
    "preferred name",
    "what to call them",
    "pronouns",
    "timezone",
    "notes",
    "email",
    "phone",
    "mobile",
    "telephone",
    "contact",
    "wechat",
    "weixin",
    "telegram",
    "tg",
    "discord",
    "slack",
    "github",
    "gitlab",
    "x",
    "twitter",
    "linkedin",
    "website",
    "homepage",
    "blog",
    "address",
    "location",
    "city",
    "country",
    "company",
    "organization",
    "title",
    "role",
)
USER_FIELD_NAME_PATTERN = "(?:" + "|".join(re.escape(name) for name in USER_FIELD_NAMES) + ")"
USER_FIELD_PATTERN = re.compile(
    r"^([ \t]*(?:[-*+]|\d+\.)?[ \t]*(?:\[[ xX]\][ \t]*)?(?:>[ \t]*)?(?:#{1,6}[ \t]*)?"
    r"" + USER_FIELD_NAME_PATTERN + r"[ \t]*(?:[:：=][ \t]*))(.*\S.*)$",
    re.IGNORECASE | re.MULTILINE,
)
USER_MARKDOWN_FIELD_PATTERN = re.compile(
    r"^([ \t]*(?:[-*+]|\d+\.)?[ \t]*(?:\[[ xX]\][ \t]*)?(?:>[ \t]*)?(?:#{1,6}[ \t]*)?"
    r"(?:\*\*|__)"
    r"" + USER_FIELD_NAME_PATTERN + r"[ \t]*[:：=](?:\*\*|__)[ \t]*)"
    r"(.*\S.*)$",
    re.IGNORECASE | re.MULTILINE,
)
USER_TABLE_PATTERN = re.compile(
    r"^([ \t]*\|[ \t]*" + USER_FIELD_NAME_PATTERN + r"[ \t]*\|[ \t]*)([^\r\n|]*?\S)([ \t]*\|[^\r\n]*)$",
    re.IGNORECASE | re.MULTILINE,
)
TOOLS_FIELD_PATTERN = re.compile(
    r"^([ \t]*(?:[-*+]|\d+\.)?[ \t]*(?:host|hostname|server|proxy|path|socket|home|cache|config)[ \t]*(?:[:：=][ \t]*))(.*\S.*)$",
    re.IGNORECASE | re.MULTILINE,
)

MEMORY_PII_LINE_PATTERNS = [
    re.compile(r"^[ \t]*[-*+]?\s*(?:contact|email|phone|wechat|telegram|address)[ \t]*[:：=].*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^[ \t]*[-*+]?\s*(?:name|full name|nickname|display name|preferred name)[ \t]*[:：=].*$", re.IGNORECASE | re.MULTILINE),
]

USER_EMPTY_PLACEHOLDER_PATTERN = re.compile(
    r"[:：=]\s*(?:_+|\[?\s*to\s+be\s+filled\s*\]?|\.{3,}|…+|\{\{[^}]*\}\})\s*$",
    re.IGNORECASE | re.MULTILINE,
)
CLEAN_MEMORY_PII_LINES = "memory_pii_lines"
CLEAN_INLINE_PII = "inline_pii"
CLEAN_TOOLS_PATTERNS = "tools_patterns"
CLEAN_TOOLS_FIELDS = "tools_fields"
CLEAN_USER_FIELDS_TO_FILL = "user_fields_to_fill"
CLEAN_USER_FIELDS_REDACTED = "user_fields_redacted"
CLEAN_COLLAPSE_BLANKS = "collapse_blanks"
CLEAN_STOP_IF_BLANK_USER_TEMPLATE = "stop_if_blank_user_template"

MODE_CLEAN_STEPS = {
    "memory": (CLEAN_MEMORY_PII_LINES, CLEAN_INLINE_PII, CLEAN_COLLAPSE_BLANKS),
    "heartbeat": (CLEAN_TOOLS_PATTERNS, CLEAN_INLINE_PII),
    "tools": (CLEAN_TOOLS_FIELDS, CLEAN_TOOLS_PATTERNS),
    "user_template": (CLEAN_STOP_IF_BLANK_USER_TEMPLATE, CLEAN_USER_FIELDS_TO_FILL, CLEAN_INLINE_PII),
    "workspace_soul": (CLEAN_USER_FIELDS_REDACTED, CLEAN_TOOLS_PATTERNS, CLEAN_INLINE_PII),
    "workspace_agents": (CLEAN_TOOLS_PATTERNS, CLEAN_INLINE_PII),
    "generic": (CLEAN_INLINE_PII,),
}


__all__ = [
    "CLEAN_COLLAPSE_BLANKS",
    "CLEAN_INLINE_PII",
    "CLEAN_MEMORY_PII_LINES",
    "CLEAN_STOP_IF_BLANK_USER_TEMPLATE",
    "CLEAN_TOOLS_FIELDS",
    "CLEAN_TOOLS_PATTERNS",
    "CLEAN_USER_FIELDS_REDACTED",
    "CLEAN_USER_FIELDS_TO_FILL",
    "MEMORY_PII_LINE_PATTERNS",
    "MODE_CLEAN_STEPS",
    "SPECIAL_CLEAN_FILENAMES",
    "SPECIAL_CLEAN_RELATIVE_FILES",
    "TOOLS_FIELD_PATTERN",
    "TOOLS_PATTERNS",
    "USER_EMPTY_PLACEHOLDER_PATTERN",
    "USER_FIELD_NAME_PATTERN",
    "USER_FIELD_NAMES",
    "USER_FIELD_PATTERN",
    "USER_MARKDOWN_FIELD_PATTERN",
    "USER_TABLE_PATTERN",
]
