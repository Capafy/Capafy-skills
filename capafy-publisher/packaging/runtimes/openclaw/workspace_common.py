from __future__ import annotations

import re

from packaging._shared.common.home import safe_expanduser_path


OPENCLAW_ROOT = safe_expanduser_path("~/.openclaw")
AGENTS_SKILLS_ROOT = safe_expanduser_path("~/.agents/skills")
OPENCLAW_STAGE_ROOT_FILES = ("openclaw.json",)
OPENCLAW_CRON_FILE = "cron/jobs.json"
OPENCLAW_CRON_DISPLAY_PATH = ".openclaw/cron/jobs.json"
OPENCLAW_CRON_UNIT_PREFIX = ".openclaw/cron/"
OPENCLAW_SELECTED_CRON_IDS_METADATA_KEY = "selected_openclaw_cron_ids_json"
OPENCLAW_EXTENSIONS_DIRNAME = "extensions"
OPENCLAW_RUNTIME_STATE_DIRS = ("agents", "identity")
OPENCLAW_GENERIC_PATH_PARTS = {
    "models",
    "entries",
    "headers",
    "config",
    "defaults",
    "installs",
    "install",
    "skills",
    "tools",
    "plugins",
    "agents",
    "media",
    "audio",
    "message",
    "crosscontext",
}
WORKSPACE_ROOT_DOCS = (
    "AGENTS.md",
    "SOUL.md",
    "TOOLS.md",
    "USER.md",
    "HEARTBEAT.md",
    "MEMORY.md",
    "memory.md",
    "README.md",
)
WORKSPACE_SKILL_SUBDIRS = ("skills", ".claude/skills", ".agents/skills")
CRON_PATH_NAME_SANITIZE_PATTERN = re.compile(r"[\\/#]+")
CRON_PATH_SPACE_PATTERN = re.compile(r"\s+")
DELIVERY_SAFE_SCALAR_KEYS = {"mode", "channel", "format", "template"}
DELIVERY_SAFE_CONTAINER_KEYS = {"headers", "retry"}


__all__ = [
    "AGENTS_SKILLS_ROOT",
    "OPENCLAW_CRON_DISPLAY_PATH",
    "OPENCLAW_CRON_FILE",
    "OPENCLAW_CRON_UNIT_PREFIX",
    "OPENCLAW_EXTENSIONS_DIRNAME",
    "OPENCLAW_GENERIC_PATH_PARTS",
    "OPENCLAW_ROOT",
    "OPENCLAW_RUNTIME_STATE_DIRS",
    "OPENCLAW_SELECTED_CRON_IDS_METADATA_KEY",
    "OPENCLAW_STAGE_ROOT_FILES",
    "WORKSPACE_ROOT_DOCS",
    "WORKSPACE_SKILL_SUBDIRS",
    "CRON_PATH_NAME_SANITIZE_PATTERN",
    "CRON_PATH_SPACE_PATTERN",
    "DELIVERY_SAFE_CONTAINER_KEYS",
    "DELIVERY_SAFE_SCALAR_KEYS",
]
