from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from packaging.configure.sensitive.config_redact import (
    redact_env_file as _redact_env_file,
    redact_env_stage_config as _redact_env_stage_config,
    redact_json_local_config as _redact_json_local_config,
    redact_json_stage_config as _redact_json_stage_config,
    redact_toml_local_config as _redact_toml_local_config,
    redact_toml_stage_config as _redact_toml_stage_config,
)
from packaging.configure.sensitive.text_redact import redact_markdown_instruction as _redact_markdown_instruction


SourceAwareRedactionStrategy = Callable[[Path, Optional[str]], int]
RedactionStrategy = Callable[[Path], int]


REDACTION_STRATEGIES_WITH_SOURCE: dict[str, SourceAwareRedactionStrategy] = {
    "env_file": _redact_env_file,
    "json_local_config": _redact_json_local_config,
    "json_stage_config": _redact_json_stage_config,
    "toml_local_config": _redact_toml_local_config,
}
REDACTION_STRATEGIES: dict[str, RedactionStrategy] = {
    "env_stage_config": _redact_env_stage_config,
    "markdown_instruction": _redact_markdown_instruction,
    "pii_clean": _redact_markdown_instruction,
    "toml_stage_config": _redact_toml_stage_config,
}


def apply_redaction_strategy(strategy: str, path: Path, *, source: str | None = None) -> int:
    if strategy in REDACTION_STRATEGIES_WITH_SOURCE:
        return REDACTION_STRATEGIES_WITH_SOURCE[strategy](path, source)
    if strategy in REDACTION_STRATEGIES:
        handler = REDACTION_STRATEGIES[strategy]
        return handler(path)
    raise ValueError(f"unknown redact strategy: {strategy}")


__all__ = [
    "REDACTION_STRATEGIES",
    "REDACTION_STRATEGIES_WITH_SOURCE",
    "RedactionStrategy",
    "SourceAwareRedactionStrategy",
    "apply_redaction_strategy",
]
