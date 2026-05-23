from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from packaging.configure.candidate import Candidate
from packaging.configure.contracts import SourceKind, UrlProxyPair
from packaging.configure.runtimes.codex.dotenv import (
    dotenv_has_any_value,
    dotenv_has_key_value,
    upsert_dotenv_key_text,
)
from packaging.configure.runtimes.codex.provider_scan import (
    codex_config_metadata,
    scan_toml_providers,
)
from packaging.configure.runtimes.codex.url_proxy_candidates import (
    annotate_candidates_with_config_metadata,
    codex_login_state_candidates,
    codex_platform_key_mode_candidate,
    has_non_openai_selected_provider,
    official_process_env_fallback_candidates,
    should_build_codex_platform_key_mode,
    usable_process_env_value,
)
from packaging.configure.runtimes.codex.url_proxy_pairs import (
    build_codex_url_proxy_pairs,
)
from packaging.configure.url_proxy.base import RuntimeContract, ScanContext
from packaging.configure.runtimes.codex.auth import CODEX_AUTH_OVERRIDE_ENV_KEY, CODEX_AUTH_PROVIDER_NAME
from packaging.configure.url_proxy.scanner_utils import (
    UrlProxyFieldSet,
    scan_dotenv,
    resolve_process_env_refs,
)

logger = logging.getLogger(__name__)

_API_KEY_FIELDS = frozenset({"OPENAI_API_KEY"})
_BASE_URL_FIELDS = frozenset({"base_url", "OPENAI_BASE_URL", "openai_base_url"})
_ID = "codex"
_OFFICIAL_PROVIDER_NAME = CODEX_AUTH_PROVIDER_NAME


class CodexRuntime(RuntimeContract):
    runtime_id = _ID
    display_name = "Codex"
    applicable_targets = frozenset({"codex"})

    def scan(self, ctx: ScanContext) -> list[Candidate]:
        candidates: list[Candidate] = []
        toml_env_keys: set[str] = set()


        candidates.extend(scan_toml_providers(ctx, toml_env_keys))
        selected_provider_blocked = has_non_openai_selected_provider(candidates)


        all_key_fields = _API_KEY_FIELDS | toml_env_keys
        field_set = UrlProxyFieldSet(api_key_fields=all_key_fields, base_url_fields=_BASE_URL_FIELDS)
        self._inject_auth_json_key_if_no_local_key(
            ctx,
            all_key_fields,
            selected_provider_blocked=selected_provider_blocked,
        )
        for relpath in (".codex/.env", ".env"):
            candidates.extend(scan_dotenv(
                ctx.staging_root / relpath, relpath,
                fields=field_set,
            ))


        existing = {c.field for c in candidates if c.source_kind in {SourceKind.FILE, SourceKind.PROCESS_ENV}}
        candidates.extend(resolve_process_env_refs(
            ctx.staging_root, ctx.process_env,
            existing_fields=existing,
            fields=field_set,
        ))
        existing = {c.field for c in candidates if c.source_kind in {SourceKind.FILE, SourceKind.PROCESS_ENV}}
        candidates.extend(self._scan_official_process_env_fallback(ctx, existing))


        candidates.extend(self._detect_login_state(
            ctx,
            candidates,
            selected_provider_blocked=selected_provider_blocked,
        ))
        if self._should_build_platform_key_mode(
            ctx,
            candidates,
            selected_provider_blocked=selected_provider_blocked,
        ):
            candidates.append(self._platform_key_mode_candidate())
        return self._with_config_metadata(ctx, candidates)

    def pair(self, candidates: list[Candidate]) -> list[UrlProxyPair]:
        return build_codex_url_proxy_pairs(candidates)

    def _scan_official_process_env_fallback(
        self,
        ctx: ScanContext,
        existing_fields: set[str],
    ) -> list[Candidate]:
        return official_process_env_fallback_candidates(
            config_exists=(ctx.staging_root / ".codex" / "config.toml").is_file(),
            process_env=ctx.process_env,
            existing_fields=existing_fields,
            auth_override_env_key=CODEX_AUTH_OVERRIDE_ENV_KEY,
        )

    @staticmethod
    def _usable_process_env_value(ctx: ScanContext, field: str) -> str:
        return usable_process_env_value(ctx.process_env, field)

    def _inject_auth_json_key_if_no_local_key(
        self,
        ctx: ScanContext,
        key_fields: frozenset[str],
        *,
        selected_provider_blocked: bool = False,
    ) -> None:
        if not key_fields:
            return
        if selected_provider_blocked:
            return
        if self._has_local_key_value(ctx, key_fields):
            return
        if self._usable_process_env_value(ctx, CODEX_AUTH_OVERRIDE_ENV_KEY):
            return

        from packaging.configure.runtimes.codex.auth import codex_auth_api_key_value, codex_auth_oauth_detected

        auth_key = codex_auth_api_key_value(ctx.staging_root, ctx.stage_plan)
        if not auth_key:
            return
        if codex_auth_oauth_detected(ctx.staging_root, ctx.stage_plan):
            return
        env_path = ctx.staging_root / ".codex" / ".env"
        if self._has_local_dotenv_value(ctx, auth_key):
            return
        env_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            text = env_path.read_text(encoding="utf-8") if env_path.is_file() else ""
        except OSError:
            text = ""
        env_path.write_text(upsert_dotenv_key_text(text, "OPENAI_API_KEY", auth_key), encoding="utf-8")

    def _has_local_key_value(self, ctx: ScanContext, key_fields: frozenset[str]) -> bool:
        for key in key_fields:
            value = self._usable_process_env_value(ctx, key)
            if value:
                return True
        for relpath in (".codex/.env", ".env"):
            if dotenv_has_key_value(ctx.staging_root / relpath, key_fields):
                return True
        return False

    def _has_local_dotenv_value(self, ctx: ScanContext, expected_value: str) -> bool:
        return (
            dotenv_has_any_value(ctx.staging_root / ".codex" / ".env", expected_value)
            or dotenv_has_any_value(ctx.staging_root / ".env", expected_value)
        )

    def _with_config_metadata(self, ctx: ScanContext, candidates: list[Candidate]) -> list[Candidate]:
        metadata = codex_config_metadata(ctx)
        return annotate_candidates_with_config_metadata(
            candidates,
            metadata,
            official_provider_name=_OFFICIAL_PROVIDER_NAME,
        )

    def rewrite(self, staging_root: Path, pairs: list[UrlProxyPair]) -> None:
        from packaging.configure.runtimes.codex.rewrite import finalize_codex_rewrites, handle_codex_rewrite_field
        from packaging.configure.url_proxy.rewriter import apply_url_proxy_to_staging

        apply_url_proxy_to_staging(
            staging_root,
            pairs,
            field_rewrite_hook=handle_codex_rewrite_field,
            finalize_hook=finalize_codex_rewrites,
        )



    def _detect_login_state(
        self,
        ctx: ScanContext,
        existing: list[Candidate],
        *,
        selected_provider_blocked: bool = False,
    ) -> list[Candidate]:
        from packaging.configure.runtimes.codex.auth import (
            codex_access_token_env_detected,
            codex_auth_api_key_value,
            codex_auth_oauth_detected,
        )

        codex_api_key = self._usable_process_env_value(ctx, CODEX_AUTH_OVERRIDE_ENV_KEY)
        auth_key = codex_auth_api_key_value(
            ctx.staging_root,
            ctx.stage_plan,
            process_env=ctx.process_env,
        )
        oauth_detected = (
            False if codex_api_key
            else codex_access_token_env_detected(ctx.process_env)
            or codex_auth_oauth_detected(ctx.staging_root, ctx.stage_plan)
        )
        return codex_login_state_candidates(
            existing=existing,
            auth_key=auth_key,
            oauth_detected=oauth_detected,
            selected_provider_blocked=selected_provider_blocked,
            has_local_dotenv_value=bool(auth_key and self._has_local_dotenv_value(ctx, auth_key)),
        )

    def _should_build_platform_key_mode(
        self,
        ctx: ScanContext,
        existing: list[Candidate],
        *,
        selected_provider_blocked: bool = False,
    ) -> bool:
        if ctx.target_id != _ID:
            return False
        if selected_provider_blocked or has_non_openai_selected_provider(existing):
            return False
        if any(
            candidate.role in {"api_key", "synthesized_api_key"}
            and str(candidate.value or "").strip()
            for candidate in existing
        ):
            return False

        from packaging.configure.runtimes.codex.auth import codex_auth_api_key_value

        auth_key = codex_auth_api_key_value(
            ctx.staging_root,
            ctx.stage_plan,
            process_env=ctx.process_env,
        )
        return should_build_codex_platform_key_mode(
            target_id=ctx.target_id,
            existing=existing,
            selected_provider_blocked=selected_provider_blocked,
            auth_key=auth_key,
            has_local_auth_dotenv_value=bool(auth_key and self._has_local_dotenv_value(ctx, auth_key)),
        )

    @staticmethod
    def _platform_key_mode_candidate() -> Candidate:
        return codex_platform_key_mode_candidate()



    def rewrite_confirmed(self, staging_root: Path, reviewed_scan: dict[str, Any]) -> dict[str, Any]:
        from packaging.configure.runtimes.codex.provider import rewrite_codex_confirmed_providers
        return rewrite_codex_confirmed_providers(staging_root, reviewed_scan)


__all__ = ["CodexRuntime"]
