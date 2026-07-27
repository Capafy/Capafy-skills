from __future__ import annotations

import os
from pathlib import Path

from packaging._shared.common.home import safe_expanduser_path


OPENCLAW_ROOT = safe_expanduser_path("~/.openclaw")
AGENTS_SKILLS_ROOT = safe_expanduser_path("~/.agents/skills")
OPENCLAW_CONFIG_PATH_ENV = "OPENCLAW_CONFIG_PATH"
OPENCLAW_STATE_DIR_ENV = "OPENCLAW_STATE_DIR"
OPENCLAW_STAGE_ROOT_FILES = ("openclaw.json",)
OPENCLAW_MAIN_AGENT_MODELS_FILE = "agents/main/agent/models.json"
OPENCLAW_OPTIONAL_STAGE_ROOT_FILES = (".env", OPENCLAW_MAIN_AGENT_MODELS_FILE)
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
DELIVERY_SAFE_SCALAR_KEYS = {"mode", "channel", "format", "template"}
DELIVERY_SAFE_CONTAINER_KEYS = {"headers", "retry"}


def resolve_openclaw_config_source(
    *,
    openclaw_root: Path = OPENCLAW_ROOT,
) -> Path:
    configured = str(os.environ.get(OPENCLAW_CONFIG_PATH_ENV, "") or "").strip()
    if configured:
        return safe_expanduser_path(configured)

    state_dir = str(os.environ.get(OPENCLAW_STATE_DIR_ENV, "") or "").strip()
    if state_dir:
        state_root = safe_expanduser_path(state_dir)
        return state_root / "openclaw.json"

    openclaw_base = safe_expanduser_path(openclaw_root)
    return openclaw_base / "openclaw.json"


def resolve_openclaw_state_root(
    *,
    openclaw_root: Path = OPENCLAW_ROOT,
) -> Path:
    configured = str(os.environ.get(OPENCLAW_STATE_DIR_ENV, "") or "").strip()
    if configured:
        return safe_expanduser_path(configured)
    return safe_expanduser_path(openclaw_root)


__all__ = [
    "AGENTS_SKILLS_ROOT",
    "OPENCLAW_CONFIG_PATH_ENV",
    "OPENCLAW_MAIN_AGENT_MODELS_FILE",
    "OPENCLAW_OPTIONAL_STAGE_ROOT_FILES",
    "OPENCLAW_GENERIC_PATH_PARTS",
    "OPENCLAW_ROOT",
    "OPENCLAW_RUNTIME_STATE_DIRS",
    "OPENCLAW_STAGE_ROOT_FILES",
    "WORKSPACE_ROOT_DOCS",
    "WORKSPACE_SKILL_SUBDIRS",
    "DELIVERY_SAFE_CONTAINER_KEYS",
    "DELIVERY_SAFE_SCALAR_KEYS",
    "OPENCLAW_STATE_DIR_ENV",
    "resolve_openclaw_config_source",
    "resolve_openclaw_state_root",
]
