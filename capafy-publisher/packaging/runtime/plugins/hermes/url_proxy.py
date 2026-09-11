from __future__ import annotations

from pathlib import Path

from packaging.config.yaml_loader import safe_yaml_mapping_loads
from packaging.runtime.plugins.support import invalid_text_config_error
from packaging.runtime.contracts import LlmRoute
from packaging.runtime.plugins.hermes.route_scan import scan_current_hermes_route
from packaging.runtime.contracts import RuntimeContract, ScanContext
from packaging.runtime.plugins.hermes.config import resolve_hermes_home


def _load_hermes_config(config_path: Path) -> dict:
    try:
        return safe_yaml_mapping_loads(config_path.read_text(encoding="utf-8"))
    except (OSError, RuntimeError, ValueError) as exc:
        raise invalid_text_config_error(
            "Hermes config",
            "YAML",
            ".hermes/config.yaml",
            str(exc),
        ) from exc


class HermesRuntime(RuntimeContract):
    def routes(self, ctx: ScanContext) -> list[LlmRoute]:
        hermes_home = (
            ctx.user_home / ".hermes"
            if ctx.user_home is not None
            else resolve_hermes_home()
        )
        config_path = hermes_home / "config.yaml"
        if not config_path.is_file():
            return []
        config = _load_hermes_config(config_path)
        return scan_current_hermes_route(config)


__all__ = ["HermesRuntime"]
