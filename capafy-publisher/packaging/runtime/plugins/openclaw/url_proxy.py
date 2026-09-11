from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from packaging.runtime.contracts import LlmRoute
from packaging.runtime.contracts import RuntimeContract, ScanContext
from packaging.runtime.plugins.support import invalid_json_config_error
from packaging.runtime.plugins.openclaw.route_scan import (
    OPENCLAW_CONFIG_REL,
    OPENCLAW_MAIN_MODELS_REL,
    scan_current_openclaw_route,
    selected_model_environment_name,
)
from packaging.runtime.plugins.openclaw.workspace_paths import (
    resolve_openclaw_config_source,
    resolve_openclaw_state_root,
)


def _invalid_config_error(exc: json.JSONDecodeError, relpath: str = OPENCLAW_CONFIG_REL) -> ValueError:
    return invalid_json_config_error("OpenClaw config", relpath, exc)


def _load_json_file(path: Path, relpath: str) -> Optional[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return None
    except json.JSONDecodeError as exc:
        raise _invalid_config_error(exc, relpath) from exc
    return payload if isinstance(payload, dict) else None


class OpenClawRuntime(RuntimeContract):
    def os_fallback_environment_names(self) -> frozenset[str]:
        config_path = resolve_openclaw_config_source()
        config = _load_json_file(config_path, OPENCLAW_CONFIG_REL)
        if not isinstance(config, dict):
            return frozenset()
        name = selected_model_environment_name(config)
        return frozenset({name}) if name else frozenset()

    def routes(self, ctx: ScanContext) -> list[LlmRoute]:
        openclaw_root = ctx.user_home / ".openclaw" if ctx.user_home is not None else None
        state_root = (
            resolve_openclaw_state_root(openclaw_root=openclaw_root)
            if openclaw_root is not None
            else resolve_openclaw_state_root()
        )
        config_path = resolve_openclaw_config_source(openclaw_root=state_root)
        models_path = state_root / "agents" / "main" / "agent" / "models.json"

        models_payload = (
            _load_json_file(models_path, OPENCLAW_MAIN_MODELS_REL)
            if models_path.is_file()
            else None
        )
        root_config = (
            _load_json_file(config_path, OPENCLAW_CONFIG_REL)
            if config_path.is_file()
            else None
        )
        return scan_current_openclaw_route(
            root_config or {},
            models_payload=models_payload,
            process_env=ctx.process_env,
        )


__all__ = ["OpenClawRuntime"]
