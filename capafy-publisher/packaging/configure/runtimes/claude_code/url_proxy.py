from __future__ import annotations

from pathlib import Path
from typing import Any

from packaging._shared.common.constants import ANTHROPIC_OFFICIAL_URL
from packaging._shared.common.url_values import normalize_http_url_candidate
from packaging.configure.candidate import Candidate
from packaging.configure.contracts import FieldLocation, PlanField, SourceKind, UrlProxyPair
from packaging.configure.env_values import usable_process_env_value
from packaging.configure.sensitive.placeholders import build_placeholder
from packaging.configure.sensitive.literals import (
    looks_like_platform_managed_placeholder_value,
)
from packaging.configure.staging.strip.fallback import replace_values_in_staging
from packaging.configure.runtimes.claude_code.auth import (
    CLAUDE_AUTH_ENV_KEY,
    CLAUDE_AUTH_TOKEN_ENV_KEY,
    CLAUDE_BASE_URL_ENV_KEY,
)
from packaging.configure.runtimes.claude_code.url_proxy_candidates import (
    API_KEY_FIELD_ORDER,
    BASE_URL_FIELD_ORDER,
    SETTINGS_SCAN_RELPATHS as _SETTINGS_SCAN_RELPATHS,
    annotate_candidates_with_settings_model,
    select_preferred_candidate,
)
from packaging.configure.runtimes.claude_code.settings_json import (
    SETTINGS_RELPATH,
    write_settings_env_placeholders,
    write_settings_model_and_prune_env_models,
)
from packaging.configure.url_proxy.base import RuntimeContract, ScanContext
from packaging.configure.url_proxy.scanner_utils import (
    UrlProxyFieldSet,
    scan_json_config,
    resolve_process_env_refs,
)

_API_KEY_FIELDS = frozenset({CLAUDE_AUTH_ENV_KEY, CLAUDE_AUTH_TOKEN_ENV_KEY})
_FIELD_SET = UrlProxyFieldSet(
    api_key_fields=_API_KEY_FIELDS,
    base_url_fields=frozenset({CLAUDE_BASE_URL_ENV_KEY}),
)
_SERVICE = "Anthropic"
_ID = "claude_code"
_API_FORMAT = "anthropic-messages"


class ClaudeCodeRuntime(RuntimeContract):
    runtime_id = _ID
    display_name = "Claude Code"
    applicable_targets = frozenset({"claude_code"})

    def scan(self, ctx: ScanContext) -> list[Candidate]:
        candidates: list[Candidate] = []


        for relpath in _SETTINGS_SCAN_RELPATHS:
            candidates.extend(scan_json_config(
                ctx.staging_root / relpath,
                relpath,
                fields=_FIELD_SET,
                excluded_prefixes=("hooks", "providers"),
            ))


        existing = {c.field for c in candidates if c.source_kind in {SourceKind.FILE, SourceKind.PROCESS_ENV}}
        candidates.extend(resolve_process_env_refs(
            ctx.staging_root, ctx.process_env,
            existing_fields=existing,
            fields=_FIELD_SET,
        ))
        existing = {c.field for c in candidates if c.source_kind in {SourceKind.FILE, SourceKind.PROCESS_ENV}}
        candidates.extend(self._scan_canonical_process_env_fallback(ctx, existing))


        candidates.extend(self._detect_login_state(ctx, candidates))
        if (
            ctx.target_id == _ID
            and not any(c.role in {"api_key", "synthesized_api_key"} and str(c.value or "").strip() for c in candidates)
        ):
            candidates.append(Candidate(
                role="synthesized_api_key",
                field=CLAUDE_AUTH_TOKEN_ENV_KEY,
                value="",
                source_kind=SourceKind.SYNTHESIZED,
                source_relpath="",
            ))
        return annotate_candidates_with_settings_model(candidates, ctx.staging_root, ctx.process_env)

    @staticmethod
    def _scan_canonical_process_env_fallback(
        ctx: ScanContext,
        existing_fields: set[str],
    ) -> list[Candidate]:
        if not (ctx.staging_root / SETTINGS_RELPATH).is_file():
            return []

        candidates: list[Candidate] = []
        for field in (CLAUDE_AUTH_TOKEN_ENV_KEY, CLAUDE_AUTH_ENV_KEY):
            value = usable_process_env_value(ctx.process_env, field)
            if value and field not in existing_fields:
                candidates.append(Candidate(
                    role="api_key",
                    field=field,
                    value=value,
                    source_kind=SourceKind.PROCESS_ENV,
                    source_relpath="",
                    location=None,
                    extra={"canonical_process_env_fallback": True},
                ))

        base_url = usable_process_env_value(ctx.process_env, CLAUDE_BASE_URL_ENV_KEY)
        normalized_url = normalize_http_url_candidate(base_url) if base_url else ""
        if normalized_url and CLAUDE_BASE_URL_ENV_KEY not in existing_fields:
            candidates.append(Candidate(
                role="base_url",
                field=CLAUDE_BASE_URL_ENV_KEY,
                value=normalized_url,
                source_kind=SourceKind.PROCESS_ENV,
                source_relpath="",
                location=None,
                extra={"canonical_process_env_fallback": True},
            ))
        return candidates

    def pair(self, candidates: list[Candidate]) -> list[UrlProxyPair]:
        key_candidate = select_preferred_candidate(
            candidates,
            roles={"api_key", "synthesized_api_key"},
            field_order=API_KEY_FIELD_ORDER,
        )
        if key_candidate is None:
            return []
        url_candidate = select_preferred_candidate(
            candidates,
            roles={"base_url"},
            field_order=BASE_URL_FIELD_ORDER,
        )

        official_url = str(key_candidate.extra.get("official_url", "") or "").strip() or ANTHROPIC_OFFICIAL_URL
        key_field = self._settings_plan_field(
            field=key_candidate.field,
            value=key_candidate.value,
            source_kind=key_candidate.source_kind,
            locator=(url_candidate.value if url_candidate is not None else official_url),
        )
        if url_candidate is None:
            url_field = self._settings_plan_field(
                field=CLAUDE_BASE_URL_ENV_KEY,
                value=official_url,
                source_kind=SourceKind.SYNTHESIZED,
                locator=official_url,
                value_type="url",
            )
        else:
            url_field = self._settings_plan_field(
                field=CLAUDE_BASE_URL_ENV_KEY,
                value=url_candidate.value,
                source_kind=url_candidate.source_kind,
                locator=url_candidate.value,
                value_type="url",
            )

        model_source = key_candidate.extra.get("model_source")
        model_plan_field: PlanField | None = None
        if isinstance(model_source, dict) and model_source.get("kind") == "process_env":
            model_env_field = str(model_source.get("field", "") or "").strip()
            model_value = str(key_candidate.extra.get("model", "") or "").strip()
            if model_env_field and model_value:
                model_plan_field = self._settings_plan_field(
                    field=model_env_field,
                    value=model_value,
                    source_kind=SourceKind.PROCESS_ENV,
                    locator=model_value,
                    value_type="model",
                )

        return [
            UrlProxyPair(
                contract_id=_ID,
                service=_SERVICE,
                group=SETTINGS_RELPATH,
                key=key_field,
                url=url_field,
                is_synthesized=key_field.source_kind == SourceKind.SYNTHESIZED,
                model=str(key_candidate.extra.get("model", "") or "").strip(),
                model_field=model_plan_field,
                api_format=_API_FORMAT,
            )
        ]

    @staticmethod
    def _settings_plan_field(
        *,
        field: str,
        value: str,
        source_kind: SourceKind,
        locator: str,
        value_type: str = "api_key",
    ) -> PlanField:
        return PlanField(
            field=field,
            service=_SERVICE,
            source_kind=source_kind,
            source_relpath=SETTINGS_RELPATH,
            location=FieldLocation(fmt="json", json_pointer=f"/env/{field}"),
            original_value=value,
            placeholder=build_placeholder(
                _SERVICE,
                SETTINGS_RELPATH,
                field=field,
                locator=locator,
                value_type=value_type,
            ),
            reviewed_source=SETTINGS_RELPATH,
            reviewed_source_detail=f"json:/env/{field}",
            reviewed_occurrence_index=1,
        )

    def rewrite(self, staging_root: Path, pairs: list[UrlProxyPair]) -> None:
        file_candidates = self._file_candidates_for_rewrite(staging_root)
        for pair in pairs:
            self._write_settings_env_placeholders(staging_root, pair)
            if pair.model:
                write_settings_model_and_prune_env_models(staging_root, pair.model)
            self._strip_candidate_file_values(staging_root, pair, file_candidates)

    @staticmethod
    def _file_candidates_for_rewrite(staging_root: Path) -> list[Candidate]:
        candidates: list[Candidate] = []
        for relpath in _SETTINGS_SCAN_RELPATHS:
            candidates.extend(scan_json_config(
                staging_root / relpath,
                relpath,
                fields=_FIELD_SET,
                excluded_prefixes=("hooks", "providers"),
            ))
        return candidates

    @staticmethod
    def _write_settings_env_placeholders(staging_root: Path, pair: UrlProxyPair) -> None:
        write_settings_env_placeholders(
            staging_root,
            key_field=pair.key.field,
            key_placeholder=pair.key.placeholder,
            url_placeholder=pair.url.placeholder,
            api_key_fields=_API_KEY_FIELDS,
            canonical_base_url_field=CLAUDE_BASE_URL_ENV_KEY,
        )

    @staticmethod
    def _strip_candidate_file_values(staging_root: Path, pair: UrlProxyPair, candidates: list[Candidate]) -> None:
        replacements = [
            (
                candidate.value,
                pair.url.placeholder if candidate.role == "base_url" else pair.key.placeholder,
            )
            for candidate in candidates
            if candidate.source_kind == SourceKind.FILE and candidate.value
        ]
        if not replacements:
            return
        replace_values_in_staging(staging_root, replacements)

    def _detect_login_state(self, ctx: ScanContext, existing: list[Candidate]) -> list[Candidate]:
        from packaging.configure.runtimes.claude_code.auth import (
            claude_auth_configured_key,
            claude_auth_login_detected,
            claude_oauth_token_env_detected,
        )

        field, value, base_url = claude_auth_configured_key(ctx.staging_root)
        if field and value:
            return [Candidate(
                role="synthesized_api_key",
                field=field,
                value=value,
                source_kind=SourceKind.SYNTHESIZED,
                source_relpath="",
                extra={
                    "configured_auth_key": True,
                    "official_url": base_url or ANTHROPIC_OFFICIAL_URL,
                },
            )]

        if not (
            claude_oauth_token_env_detected(ctx.process_env)
            or claude_auth_login_detected(ctx.staging_root, ctx.stage_plan)
        ):
            return []
        if not any(c.field in _API_KEY_FIELDS for c in existing if c.source_kind == SourceKind.FILE):
            return [Candidate(role="synthesized_api_key", field=CLAUDE_AUTH_TOKEN_ENV_KEY, value="", source_kind=SourceKind.SYNTHESIZED, source_relpath="")]
        return []

    def rewrite_confirmed(self, staging_root: Path, reviewed_scan: dict[str, Any]) -> dict[str, Any]:
        url_proxy = reviewed_scan.get("url_proxy", [])
        if not isinstance(url_proxy, list):
            return {}
        confirmed, model = self._confirmed_url_proxy_summary(url_proxy)
        model_rewritten = False
        if model:
            model_rewritten = write_settings_model_and_prune_env_models(staging_root, model)
        summary: dict[str, Any] = {}
        if confirmed:
            summary["claude_code_confirmed_entries"] = confirmed
        if model_rewritten:
            summary["claude_code_confirmed_model_rewrites"] = 1
        return summary

    @staticmethod
    def _confirmed_url_proxy_summary(url_proxy: list[Any]) -> tuple[int, str]:
        confirmed = 0
        confirmed_model = ""
        for entry in url_proxy:
            if not isinstance(entry, dict):
                continue
            if ".claude/" not in str(entry.get("url_proxy_group", "") or entry.get("group", "")):
                continue
            confirmed += 1
            if not confirmed_model:
                confirmed_model = str(entry.get("model", "") or "").strip()
        return confirmed, confirmed_model

__all__ = ["ClaudeCodeRuntime"]
