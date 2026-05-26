from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from packaging.configure.candidate import Candidate
from packaging.configure.contracts import (
    SourceKind,
    UrlProxyPair,
)
from packaging.configure.url_proxy.base import RuntimeContract, ScanContext
from packaging.configure.runtimes.openclaw.auth_profile_materialize import (
    ensure_auth_profile_providers,
)
from packaging.configure.runtimes.openclaw.auth_profiles import load_auth_profile_keys
from packaging.configure.runtimes.openclaw.provider_pairs import pair_openclaw_provider_candidates
from packaging.configure.runtimes.openclaw.provider_scan import scan_openclaw_provider_candidates
from packaging.configure.runtimes.openclaw.provider_confirmation import (
    rewrite_openclaw_confirmed_providers,
)
from packaging.configure.runtimes.openclaw.provider_rewrite import (
    rewrite_openclaw_builtin_models_as_explicit_providers,
)
from packaging.configure.runtimes.openclaw.provider_state import (
    ensure_official_provider_skeletons,
    ensure_openclaw_provider_api_formats,
    materialize_official_provider_values,
    official_provider_names_from_login_state,
    prune_openclaw_login_state,
)
from packaging.configure.runtimes.openclaw.provider_usage import get_openclaw_providers
from packaging.configure.staging.env_preprocess import RuntimeEnvContext

logger = logging.getLogger(__name__)

_CONFIG_REL = ".openclaw/openclaw.json"


class OpenClawRuntime(RuntimeContract):
    runtime_id = "openclaw"
    display_name = "OpenClaw"
    applicable_targets = frozenset({"openclaw"})



    def prepare(self, ctx: ScanContext) -> None:
        config_path = ctx.staging_root / _CONFIG_REL
        if not config_path.is_file():
            return

        try:
            text = config_path.read_text(encoding="utf-8")
            env_context = ctx.env_context or RuntimeEnvContext(process_env=ctx.process_env)
            updated_text, _rewrite_count = rewrite_openclaw_builtin_models_as_explicit_providers(
                text,
                staging_root=ctx.staging_root,
                env_context=env_context,
            )
            config = json.loads(updated_text)
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(config, dict):
            return

        auth_keys = load_auth_profile_keys(ctx)
        auth_changed = False
        if auth_keys:
            auth_changed = ensure_auth_profile_providers(config, auth_keys)

        login_provider_names = official_provider_names_from_login_state(config)
        login_provider_changed = ensure_official_provider_skeletons(config, login_provider_names)
        login_state_changed = prune_openclaw_login_state(config)
        providers = get_openclaw_providers(config)
        skeleton_changed = False
        if not providers:
            skeleton_changed = ensure_official_provider_skeletons(config, ["publisher_openai_official"])
        api_format_changed = ensure_openclaw_provider_api_formats(config)
        providers = get_openclaw_providers(config)

        changed = (
            updated_text != text
            or auth_changed
            or login_provider_changed
            or login_state_changed
            or skeleton_changed
            or api_format_changed
        )
        changed = materialize_official_provider_values(
            providers,
            auth_keys=auth_keys,
            process_env=ctx.process_env,
        ) or changed

        if changed:
            config_path.write_text(
                json.dumps(config, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )



    def scan(self, ctx: ScanContext) -> list[Candidate]:
        config_path = ctx.staging_root / _CONFIG_REL
        if not config_path.is_file():
            return []
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        return scan_openclaw_provider_candidates(ctx, config)



    def pair(self, candidates: list[Candidate]) -> list[UrlProxyPair]:
        return pair_openclaw_provider_candidates(candidates)



    def rewrite(self, staging_root: Path, pairs: list[UrlProxyPair]) -> None:
        config_path = staging_root / _CONFIG_REL
        if not config_path.is_file():
            return
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        changed = False
        for pair in pairs:
            for plan_field in (pair.key, pair.url):
                if plan_field.source_kind != SourceKind.FILE:
                    continue
                if not plan_field.location or not plan_field.location.json_pointer:
                    continue
                parts = [p for p in plan_field.location.json_pointer.split("/") if p]
                node = config
                for part in parts[:-1]:
                    if isinstance(node, dict) and part in node:
                        node = node[part]
                    else:
                        node = None
                        break
                if isinstance(node, dict) and parts:
                    current = str(node.get(parts[-1], ""))
                    if current != plan_field.placeholder:
                        node[parts[-1]] = plan_field.placeholder
                        changed = True

        if changed:
            config_path.write_text(
                json.dumps(config, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )



    def rewrite_confirmed(self, staging_root: Path, reviewed_scan: dict[str, Any]) -> dict[str, Any]:
        return rewrite_openclaw_confirmed_providers(staging_root, reviewed_scan)


__all__ = ["OpenClawRuntime"]
