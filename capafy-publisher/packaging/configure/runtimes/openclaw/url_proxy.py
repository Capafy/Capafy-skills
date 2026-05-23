from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from packaging._shared.openclaw.official_providers import (
    OPENCLAW_OFFICIAL_PROVIDER_SPECS,
    OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME,
)
from packaging._shared.common.url_values import normalize_http_url_candidate
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
from packaging.configure.runtimes.openclaw.provider_keys import (
    collect_provider_api_key_items,
    resolve_api_key_config_value,
)
from packaging.configure.runtimes.openclaw.provider_pairs import pair_openclaw_provider_candidates
from packaging.configure.runtimes.openclaw.provider_scan import (
    get_openclaw_providers,
    scan_openclaw_provider_candidates,
)
from packaging.configure.runtimes.openclaw.provider_confirmation import (
    rewrite_openclaw_confirmed_providers,
)
from packaging.configure.runtimes.openclaw.provider_rewrite import (
    collect_openclaw_staged_dotenv_env,
    rewrite_openclaw_builtin_models_as_explicit_providers,
)


logger = logging.getLogger(__name__)

_CONFIG_REL = ".openclaw/openclaw.json"
_LOGIN_PLUGIN_STATE_KEYS = frozenset({
    "accessToken",
    "access_token",
    "apiKey",
    "api_key",
    "auth",
    "credential",
    "credentials",
    "idToken",
    "id_token",
    "login",
    "refreshToken",
    "refresh_token",
    "session",
    "token",
})
_KNOWN_LOGIN_PLUGIN_ENTRIES = frozenset({
    "github-copilot",
    "openai",
})


def _looks_like_login_plugin_entry(plugin_name: object, payload: object) -> bool:
    normalized_name = str(plugin_name or "").strip().lower()
    if not normalized_name:
        return False
    if normalized_name in _KNOWN_LOGIN_PLUGIN_ENTRIES or normalized_name.endswith("login"):
        return True
    if isinstance(payload, dict):
        if any(str(key) in _LOGIN_PLUGIN_STATE_KEYS for key in payload):
            return True
    return False


def _prune_login_state(config: dict[str, Any]) -> bool:
    changed = False
    if "auth" in config:
        config.pop("auth", None)
        changed = True

    plugins = config.get("plugins")
    if not isinstance(plugins, dict):
        return changed
    entries = plugins.get("entries")
    if not isinstance(entries, dict):
        return changed

    for plugin_name in list(entries):
        if _looks_like_login_plugin_entry(plugin_name, entries.get(plugin_name)):
            entries.pop(plugin_name, None)
            changed = True
    return changed


def _ensure_default_openai_provider_skeleton(config: dict[str, Any]) -> bool:
    spec = OPENCLAW_OFFICIAL_PROVIDER_SPECS_BY_NAME["publisher_openai_official"]
    changed = False

    models = config.get("models")
    if isinstance(models, dict):
        providers = models.get("providers")
        if isinstance(providers, dict) and providers:
            return False
    else:
        models = {}
        config["models"] = models
        changed = True
    if str(models.get("mode", "") or "").strip() != "merge":
        models["mode"] = "merge"
        changed = True

    providers = models.get("providers")
    if not isinstance(providers, dict):
        providers = {}
        models["providers"] = providers
        changed = True

    provider = providers.get(spec.provider_name)
    if not isinstance(provider, dict):
        provider = {}
        providers[spec.provider_name] = provider
        changed = True

    if not str(provider.get("api", "") or "").strip():
        provider["api"] = spec.api
        changed = True
    if not normalize_http_url_candidate(str(provider.get("baseUrl", "")).strip()):
        provider["baseUrl"] = spec.base_url
        changed = True
    return changed


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
            dotenv_env = collect_openclaw_staged_dotenv_env(ctx.staging_root, text)
            updated_text, _rewrite_count = rewrite_openclaw_builtin_models_as_explicit_providers(
                text,
                dotenv_env=dotenv_env,
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

        login_state_changed = _prune_login_state(config)
        skeleton_changed = _ensure_default_openai_provider_skeleton(config)
        providers = get_openclaw_providers(config)

        changed = updated_text != text or auth_changed or login_state_changed or skeleton_changed
        for spec in OPENCLAW_OFFICIAL_PROVIDER_SPECS:
            provider_name = spec.provider_name
            provider = providers.get(provider_name)
            if not isinstance(provider, dict):
                continue
            api_key_val = str(provider.get("apiKey", "")).strip()
            if str(provider.get("api", "")).strip() != spec.api:
                continue

            key_items = collect_provider_api_key_items(spec, ctx.process_env)
            if not key_items:
                profile_items = auth_keys.get(provider_name, [])
                if profile_items:
                    key_items = [
                        {"value": value, "env_name": "", "field_aliases": []}
                        for value in profile_items
                    ]

            real_key = ""
            if key_items:
                real_key = str(key_items[0].get("value", "")).strip()
            if not real_key:
                real_key = resolve_api_key_config_value(api_key_val, ctx.process_env)

            if real_key and provider.get("apiKey") != real_key:
                provider["apiKey"] = real_key
                changed = True
            base_url = normalize_http_url_candidate(str(provider.get("baseUrl", "")).strip())
            if not base_url:
                provider["baseUrl"] = spec.base_url
                changed = True

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
