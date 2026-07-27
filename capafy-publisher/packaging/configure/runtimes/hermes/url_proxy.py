from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from packaging._shared.config_files.yaml_loader import safe_yaml_dumps, safe_yaml_mapping_loads
from packaging.configure.candidate import Candidate
from packaging.configure.contracts import UrlProxyPair
from packaging.configure.runtimes.hermes.auth_profile_materialize import ensure_hermes_official_providers
from packaging.configure.runtimes.hermes.auth_profiles import (
    hermes_oauth_keys_from_credentials,
    load_hermes_auth_profile_credentials,
)
from packaging.configure.runtimes.hermes.provider_pairs import pair_hermes_provider_candidates
from packaging.configure.runtimes.hermes.provider_normalize import normalize_hermes_provider_blocks
from packaging.configure.runtimes.hermes.provider_rewrite import (
    rewrite_hermes_provider_pairs,
)
from packaging.configure.runtimes.hermes.provider_scan import CONFIG_REL, scan_hermes_provider_candidates
from packaging.configure.staging.provider_runtime_config import ProviderRuntimeConfigContext
from packaging.configure.url_proxy.base import RuntimeContract, ScanContext


class HermesRuntime(RuntimeContract):
    runtime_id = "hermes"
    carries_provider_runtime_config = True

    def __init__(self) -> None:
        self._provider_config_context: Optional[ProviderRuntimeConfigContext] = None

    def prepare_provider_runtime_config(
        self,
        staging_root: Path,
        *,
        provider_config_context: ProviderRuntimeConfigContext,
    ) -> frozenset[str]:
        from packaging.configure.runtimes.hermes.provider_rewrite import (
            resolve_hermes_staged_env_templates,
        )

        return frozenset(
            resolve_hermes_staged_env_templates(
                staging_root,
                provider_config_context=provider_config_context,
            )
        )

    def os_fallback_environment_names(self) -> frozenset[str]:
        from packaging.configure.runtimes.hermes.official_providers import (
            HERMES_OFFICIAL_PROVIDER_SPECS,
        )

        return frozenset(
            name
            for spec in HERMES_OFFICIAL_PROVIDER_SPECS
            for name in spec.primary_env_names
            if name
        )

    def validate_review_consistency(
        self,
        staging_root: Path,
        *,
        reviewed_scan: dict[str, Any],
    ) -> None:
        from packaging.configure.runtimes.hermes.review_consistency import (
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
        field = str(getattr(field_obj, "field", "") or "").strip()
        semantic_field = field.rsplit(".", 1)[-1]
        if source != ".hermes/config.yaml" or semantic_field not in {"api_key", "base_url"}:
            return ("", "", "")
        value = str(getattr(field_obj, "original_value", "") or "").strip()
        return (source, semantic_field, value) if value else ("", "", "")

    def prepare(self, ctx: ScanContext) -> None:
        config_path = ctx.staging_root / CONFIG_REL
        self._provider_config_context = ctx.provider_config_context or ProviderRuntimeConfigContext(process_env=ctx.process_env)
        auth_credentials = load_hermes_auth_profile_credentials(ctx)
        oauth_keys = hermes_oauth_keys_from_credentials(auth_credentials)
        if not config_path.is_file():
            if not oauth_keys:
                return
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config: dict[str, Any] = {}
        else:
            try:
                config = safe_yaml_mapping_loads(config_path.read_text(encoding="utf-8"))
            except (OSError, RuntimeError, ValueError):
                return
        changed = False
        if oauth_keys:
            changed = ensure_hermes_official_providers(
                config,
                oauth_keys,
                auth_credentials=auth_credentials,
            ) or changed
        changed = normalize_hermes_provider_blocks(config) or changed
        if changed:
            config_path.write_text(safe_yaml_dumps(config), encoding="utf-8")

    def scan(self, ctx: ScanContext) -> list[Candidate]:
        config_path = ctx.staging_root / CONFIG_REL
        if not config_path.is_file():
            return []
        try:
            config = safe_yaml_mapping_loads(config_path.read_text(encoding="utf-8"))
        except (OSError, RuntimeError, ValueError):
            return []
        provider_config_context = ctx.provider_config_context or self._provider_config_context or ProviderRuntimeConfigContext(process_env=ctx.process_env)
        self._provider_config_context = provider_config_context
        return scan_hermes_provider_candidates(
            config,
            staging_root=ctx.staging_root,
            provider_config_context=provider_config_context,
            process_env=dict(ctx.process_env or {}),
        )

    def pair(self, candidates: list[Candidate]) -> list[UrlProxyPair]:
        return pair_hermes_provider_candidates(candidates)

    def rewrite(self, staging_root: Path, pairs: list[UrlProxyPair]) -> None:
        if self._provider_config_context is not None:
            from packaging.configure.runtimes.hermes.provider_rewrite import resolve_hermes_staged_env_templates

            resolve_hermes_staged_env_templates(staging_root, provider_config_context=self._provider_config_context)
            _consume_pair_env_names(staging_root, pairs, self._provider_config_context)
        rewrite_hermes_provider_pairs(staging_root, pairs)

    def rewrite_confirmed(self, staging_root: Path, reviewed_scan: dict[str, Any]) -> dict[str, Any]:
        from packaging.configure.runtimes.hermes.provider_confirmation import rewrite_hermes_confirmed_providers

        return rewrite_hermes_confirmed_providers(staging_root, reviewed_scan)


def _consume_pair_env_names(
    staging_root: Path,
    pairs: list[UrlProxyPair],
    provider_config_context: ProviderRuntimeConfigContext,
) -> None:
    from packaging._shared.config_files.yaml_loader import get_yaml_path_value, safe_yaml_mapping_loads
    from packaging.configure.env_values import env_reference_name

    from packaging.configure.runtimes.hermes.provider_scan import (
        CONFIG_REL,
        HERMES_DOTENV_RELPATHS,
        hermes_default_env_names,
        resolve_hermes_official_spec,
    )

    names: set[str] = set()
    config_path = Path(staging_root) / CONFIG_REL
    try:
        payload = safe_yaml_mapping_loads(config_path.read_text(encoding="utf-8"))
    except (OSError, RuntimeError, ValueError):
        payload = {}
    if isinstance(payload, dict):
        for pair in pairs:
            location = pair.key.location
            if location is None or location.fmt != "yaml":
                continue
            raw_key = get_yaml_path_value(payload, location.key_path)
            env_name = env_reference_name(raw_key)
            if env_name:
                names.add(env_name)
                continue
            block = get_yaml_path_value(payload, location.key_path[:-1])
            if not isinstance(block, dict):
                continue
            env_name = env_reference_name(block.get("key_env", "") or block.get("api_key_env", ""))
            if env_name:
                names.add(env_name)
                continue
            if str(raw_key or "").strip():
                continue
            default_names = frozenset(hermes_default_env_names(block, resolve_hermes_official_spec(block)))
            if not default_names:
                continue
            original_value = str(pair.key.original_value or "").strip()
            if not original_value:
                continue
            dotenv_values = provider_config_context.staged_dotenv_values(
                staging_root,
                relpaths=HERMES_DOTENV_RELPATHS,
                names=default_names,
            )
            for name, value in dotenv_values.items():
                if str(value or "").strip() == original_value:
                    names.add(name)
    if names:
        provider_config_context.consume_staged_dotenv_names(
            staging_root,
            relpaths=HERMES_DOTENV_RELPATHS,
            names=frozenset(names),
        )

__all__ = ["HermesRuntime"]
