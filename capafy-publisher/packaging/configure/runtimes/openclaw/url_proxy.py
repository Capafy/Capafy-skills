from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from packaging.configure.candidate import Candidate
from packaging.configure.config_errors import invalid_json_config_error
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
from packaging.configure.runtimes.openclaw.provider_payloads import (
    canonicalize_official_provider_aliases,
    strip_provider_runtime_metadata,
)
from packaging.configure.runtimes.openclaw.provider_scan import (
    OPENCLAW_CONFIG_REL,
    OPENCLAW_MAIN_MODELS_REL,
    scan_openclaw_provider_candidates,
)
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
from packaging.configure.staging.provider_runtime_config import ProviderRuntimeConfigContext

logger = logging.getLogger(__name__)


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


def _write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _main_models_pseudo_config(
    models_payload: dict[str, Any],
    root_config: Optional[dict[str, Any]],
) -> dict[str, Any]:
    providers = models_payload.get("providers")
    if not isinstance(providers, dict):
        return {}
    pseudo: dict[str, Any] = {"models": {"providers": providers}}
    if isinstance(root_config, dict):
        agents = root_config.get("agents")
        if isinstance(agents, dict):
            pseudo["agents"] = agents
    return pseudo


def _prepare_main_models_payload(
    payload: dict[str, Any],
    *,
    auth_keys: dict[str, list[str]],
    process_env: dict[str, str],
) -> bool:
    providers = payload.get("providers")
    if not isinstance(providers, dict):
        return False
    pseudo = {"models": {"providers": providers}}
    changed = canonicalize_official_provider_aliases(providers) > 0
    changed = strip_provider_runtime_metadata(providers) > 0 or changed
    changed = ensure_openclaw_provider_api_formats(pseudo) or changed
    changed = materialize_official_provider_values(
        providers,
        auth_keys=auth_keys,
        process_env=process_env,
    ) or changed
    return changed


def _main_models_has_providers(staging_root: Path) -> bool:
    models_path = staging_root / OPENCLAW_MAIN_MODELS_REL
    if not models_path.is_file():
        return False
    payload = _load_json_file(models_path, OPENCLAW_MAIN_MODELS_REL)
    if payload is None:
        return False
    providers = payload.get("providers")
    return isinstance(providers, dict) and bool(providers)


def _rewrite_json_placeholders(payload: dict[str, Any], pairs: list[UrlProxyPair], relpath: str) -> bool:
    changed = False
    for pair in pairs:
        for plan_field in (pair.key, pair.url):
            if plan_field.source_kind != SourceKind.FILE:
                continue
            if plan_field.source_relpath != relpath:
                continue
            if not plan_field.location or not plan_field.location.json_pointer:
                continue
            parts = [p for p in plan_field.location.json_pointer.split("/") if p]
            node: Any = payload
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
    return changed


class OpenClawRuntime(RuntimeContract):
    runtime_id = "openclaw"
    carries_provider_runtime_config = True

    def prepare_provider_runtime_config(
        self,
        staging_root: Path,
        *,
        provider_config_context: ProviderRuntimeConfigContext,
    ) -> frozenset[str]:
        from packaging.configure.runtimes.openclaw.provider_rewrite import (
            resolve_openclaw_staged_env_templates,
        )

        return frozenset(
            resolve_openclaw_staged_env_templates(
                staging_root,
                provider_config_context=provider_config_context,
            )
        )

    def os_fallback_environment_names(self) -> frozenset[str]:
        from packaging.configure.runtimes.openclaw.official_providers import (
            OPENCLAW_OFFICIAL_PROVIDER_SPECS,
        )

        return frozenset(
            name
            for spec in OPENCLAW_OFFICIAL_PROVIDER_SPECS
            for name in spec.exact_env_keys
            if name
        )

    def validate_review_consistency(
        self,
        staging_root: Path,
        *,
        reviewed_scan: dict[str, Any],
    ) -> None:
        from packaging.configure.runtimes.openclaw.review_consistency import (
            validate_review_consistency,
        )

        validate_review_consistency(staging_root, reviewed_scan=reviewed_scan)

    def semantic_field_identity(self, field_obj: Any) -> tuple[str, str, str]:
        source_identity = getattr(field_obj, "source_identity", None)
        source = str(
            source_identity()
            if callable(source_identity)
            else getattr(field_obj, "source_relpath", "")
            or ""
        ).strip()
        if source != ".openclaw/openclaw.json":
            return ("", "", "")
        field = str(getattr(field_obj, "field", "") or "").strip()
        parts = field.split(".")
        semantic_field = ""
        if len(parts) == 4 and parts[:2] == ["models", "providers"]:
            semantic_field = parts[3]
        elif "." not in field:
            semantic_field = field
        if semantic_field not in {"apiKey", "baseUrl"}:
            return ("", "", "")
        value = str(getattr(field_obj, "original_value", "") or "").strip()
        return (source, semantic_field, value) if value else ("", "", "")



    def prepare(self, ctx: ScanContext) -> None:
        config_path = ctx.staging_root / OPENCLAW_CONFIG_REL
        root_config: dict[str, Any] = {}
        auth_keys = load_auth_profile_keys(ctx)

        if config_path.is_file():
            try:
                text = config_path.read_text(encoding="utf-8")
            except OSError:
                text = ""
            provider_config_context = ctx.provider_config_context or ProviderRuntimeConfigContext(process_env=ctx.process_env)
            if text:
                try:
                    updated_text, _rewrite_count = rewrite_openclaw_builtin_models_as_explicit_providers(
                        text,
                        staging_root=ctx.staging_root,
                        provider_config_context=provider_config_context,
                    )
                    config = json.loads(updated_text)
                except json.JSONDecodeError as exc:
                    raise _invalid_config_error(exc) from exc
            else:
                updated_text = text
                config = {}
            if isinstance(config, dict):
                root_config = config

                auth_changed = False
                if auth_keys:
                    auth_changed = ensure_auth_profile_providers(config, auth_keys)

                login_provider_names = official_provider_names_from_login_state(config)
                login_provider_changed = ensure_official_provider_skeletons(config, login_provider_names)
                login_state_changed = prune_openclaw_login_state(config)
                providers = get_openclaw_providers(config)
                skeleton_changed = False
                if not providers and not _main_models_has_providers(ctx.staging_root):
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
                    _write_json_file(config_path, config)

        models_path = ctx.staging_root / OPENCLAW_MAIN_MODELS_REL
        if models_path.is_file():
            models_payload = _load_json_file(models_path, OPENCLAW_MAIN_MODELS_REL)
            if models_payload is not None and _prepare_main_models_payload(
                models_payload,
                auth_keys=auth_keys,
                process_env=ctx.process_env,
            ):
                _write_json_file(models_path, models_payload)



    def scan(self, ctx: ScanContext) -> list[Candidate]:
        config_path = ctx.staging_root / OPENCLAW_CONFIG_REL
        root_config = _load_json_file(config_path, OPENCLAW_CONFIG_REL) if config_path.is_file() else {}
        candidates: list[Candidate] = []
        if isinstance(root_config, dict):
            candidates.extend(scan_openclaw_provider_candidates(ctx, root_config))

        models_path = ctx.staging_root / OPENCLAW_MAIN_MODELS_REL
        if models_path.is_file():
            models_payload = _load_json_file(models_path, OPENCLAW_MAIN_MODELS_REL)
            if models_payload is not None:
                pseudo = _main_models_pseudo_config(models_payload, root_config)
                if pseudo:
                    candidates.extend(
                        scan_openclaw_provider_candidates(
                            ctx,
                            pseudo,
                            source_relpath=OPENCLAW_MAIN_MODELS_REL,
                            provider_field_prefix="providers",
                            provider_pointer_prefix="/providers",
                        )
                    )

        return candidates



    def pair(self, candidates: list[Candidate]) -> list[UrlProxyPair]:
        return pair_openclaw_provider_candidates(candidates)



    def rewrite(self, staging_root: Path, pairs: list[UrlProxyPair]) -> None:
        relpaths = {
            plan_field.source_relpath
            for pair in pairs
            for plan_field in (pair.key, pair.url)
            if plan_field.source_kind == SourceKind.FILE and plan_field.source_relpath
        }
        for relpath in sorted(relpaths):
            path = staging_root / relpath
            if not path.is_file():
                continue
            payload = _load_json_file(path, relpath)
            if payload is None:
                continue
            if _rewrite_json_placeholders(payload, pairs, relpath):
                _write_json_file(path, payload)



    def rewrite_confirmed(self, staging_root: Path, reviewed_scan: dict[str, Any]) -> dict[str, Any]:
        return rewrite_openclaw_confirmed_providers(staging_root, reviewed_scan)


__all__ = ["OpenClawRuntime"]
