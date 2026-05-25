from __future__ import annotations

import re
from pathlib import Path

from packaging.configure.contracts import PlanField, SourceKind, UrlProxyPair
from packaging.configure.runtimes.codex.auth import CODEX_AUTH_PROVIDER_NAME
from packaging.configure.runtimes.codex.provider_config import (
    disable_requires_openai_auth,
    ensure_model_provider,
    ensure_provider_section,
    provider_name_from_codex_section,
    provider_name_from_pair_group,
    remove_top_level_toml_key,
)
from packaging.configure.runtimes.codex.url_proxy_pairs import CODEX_CONTRACT_ID


_ENV_KEY_PATTERN = re.compile(r"^(\s*(?:export\s+)?)([A-Za-z_][A-Za-z0-9_]*)(\s*=\s*)(.*)$")


def handle_codex_rewrite_field(staging_root: Path, plan_field: PlanField, pair: UrlProxyPair) -> bool:
    return (
        _maybe_materialize_env_key(staging_root, plan_field, pair)
        or _maybe_rehome_top_level_openai_base_url(staging_root, plan_field, pair)
        or _maybe_materialize_process_env_base_url(staging_root, plan_field, pair)
        or _maybe_synthesize_provider_field(staging_root, plan_field, pair)
    )


def _maybe_materialize_env_key(
    staging_root: Path,
    plan_field: PlanField,
    pair: UrlProxyPair,
) -> bool:
    if pair.contract_id != CODEX_CONTRACT_ID:
        return False
    if plan_field != pair.key:
        return False
    if plan_field.source_kind not in {SourceKind.PROCESS_ENV, SourceKind.SYNTHESIZED}:
        return False
    if not str(plan_field.field or "").strip():
        return False
    _upsert_dotenv_key(
        staging_root / ".codex" / ".env",
        key=plan_field.field,
        value=plan_field.placeholder,
    )
    return True


def finalize_codex_rewrites(staging_root: Path, pairs: list[UrlProxyPair]) -> None:
    codex_pairs = [pair for pair in pairs if pair.contract_id == CODEX_CONTRACT_ID]
    if not codex_pairs:
        return
    for pair in codex_pairs:
        if provider_name_from_pair_group(pair.group) == CODEX_AUTH_PROVIDER_NAME:
            ensure_model_provider(
                staging_root / ".codex" / "config.toml",
                provider=CODEX_AUTH_PROVIDER_NAME,
            )
            break
    disable_requires_openai_auth(staging_root)


def _maybe_rehome_top_level_openai_base_url(
    staging_root: Path,
    plan_field: PlanField,
    pair: UrlProxyPair,
) -> bool:
    if pair.contract_id != CODEX_CONTRACT_ID:
        return False
    if plan_field.field != "openai_base_url":
        return False
    if plan_field.source_kind != SourceKind.FILE:
        return False
    location = plan_field.location
    if not location or location.fmt != "toml" or location.toml_section:
        return False
    source_relpath = plan_field.source_relpath or ".codex/config.toml"
    config_path = staging_root / source_relpath
    ensure_provider_section(
        config_path,
        provider=CODEX_AUTH_PROVIDER_NAME,
        env_key="OPENAI_API_KEY",
        base_url_placeholder=plan_field.placeholder,
        synthesize_group=False,
    )
    remove_top_level_toml_key(config_path, plan_field.field)
    return True


def _maybe_materialize_process_env_base_url(
    staging_root: Path,
    plan_field: PlanField,
    pair: UrlProxyPair,
) -> bool:
    if pair.contract_id != CODEX_CONTRACT_ID:
        return False
    if plan_field != pair.url:
        return False
    if plan_field.source_kind != SourceKind.PROCESS_ENV:
        return False
    if plan_field.field != "OPENAI_BASE_URL":
        return False
    source_relpath = plan_field.source_relpath or ".codex/config.toml"
    provider = provider_name_from_pair_group(pair.group) or CODEX_AUTH_PROVIDER_NAME
    ensure_provider_section(
        staging_root / source_relpath,
        provider=provider,
        env_key=pair.key.field or "OPENAI_API_KEY",
        base_url_placeholder=plan_field.placeholder,
        synthesize_group=pair.is_synthesized,
    )
    return True


def _maybe_synthesize_provider_field(
    staging_root: Path,
    plan_field: PlanField,
    pair: UrlProxyPair,
) -> bool:
    if pair.contract_id != CODEX_CONTRACT_ID:
        return False
    if plan_field.source_kind != SourceKind.SYNTHESIZED:
        return False
    if plan_field.field not in {"base_url", "OPENAI_BASE_URL"}:
        return False
    location = plan_field.location
    if not location or location.fmt != "toml" or not location.toml_section:
        return False
    source_relpath = plan_field.source_relpath or ".codex/config.toml"
    config_path = staging_root / source_relpath
    provider = provider_name_from_codex_section(location.toml_section)
    if not provider:
        provider = CODEX_AUTH_PROVIDER_NAME
    ensure_provider_section(
        config_path,
        provider=provider,
        env_key=pair.key.field,
        base_url_placeholder=plan_field.placeholder,
        synthesize_group=pair.is_synthesized,
    )
    return True


def _upsert_dotenv_key(file_path: Path, *, key: str, value: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        text = file_path.read_text(encoding="utf-8") if file_path.is_file() else ""
    except OSError:
        text = ""

    lines = text.splitlines(keepends=True)
    for idx, raw_line in enumerate(lines):
        line = raw_line.rstrip("\r\n")
        match = _ENV_KEY_PATTERN.match(line)
        if not match or match.group(2) != key:
            continue
        newline = "\n" if raw_line.endswith("\n") else ""
        lines[idx] = f"{match.group(1)}{key}{match.group(3)}{value}{newline}"
        file_path.write_text("".join(lines), encoding="utf-8")
        return

    if text and not text.endswith("\n"):
        text += "\n"
    file_path.write_text(f"{text}{key}={value}\n", encoding="utf-8")


__all__ = ["finalize_codex_rewrites", "handle_codex_rewrite_field"]
