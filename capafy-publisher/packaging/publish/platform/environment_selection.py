from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Mapping, Optional

from packaging.common.fs import safe_chmod
from packaging.publish.platform.url_proxy_environment import (
    ENVIRONMENT_HINT_IGNORED_NAMES,
)


ENVIRONMENT_SELECTION_VERSION = 1
_ENVIRONMENT_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{1,127}$")
_ADDITIONAL_FORBIDDEN_NAMES = frozenset(
    {
        "CAPAFY_ACCESS_TOKEN",
        "CAPAFY_TOKEN",
        "CAPAFY_PLATFORM_BASE_URL",
    }
)
FORBIDDEN_ENVIRONMENT_NAMES = frozenset(
    {
        str(name).strip().upper()
        for name in (*ENVIRONMENT_HINT_IGNORED_NAMES, *_ADDITIONAL_FORBIDDEN_NAMES)
        if str(name).strip()
    }
)
_RUNTIME_FORBIDDEN_ENVIRONMENT_NAMES = {
    "claude_code": frozenset({"ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY"}),
    "codex": frozenset({"OPENAI_BASE_URL", "OPENAI_API_KEY"}),
}


def forbidden_environment_names_for_runtime(env_id: str) -> frozenset[str]:
    normalized_env_id = str(env_id or "").strip().lower().replace("-", "_")
    if normalized_env_id == "claude":
        normalized_env_id = "claude_code"
    return frozenset(
        {
            *FORBIDDEN_ENVIRONMENT_NAMES,
            *_RUNTIME_FORBIDDEN_ENVIRONMENT_NAMES.get(normalized_env_id, frozenset()),
        }
    )


def filter_environment_names_for_runtime(
    names: tuple[str, ...],
    *,
    env_id: str,
) -> tuple[str, ...]:
    forbidden_names = forbidden_environment_names_for_runtime(env_id)
    return tuple(
        name
        for name in names
        if str(name or "").strip().upper() not in forbidden_names
    )


@dataclass(frozen=True)
class EnvironmentSelection:
    candidate_digest: str
    candidates: tuple[str, ...]
    selected: tuple[str, ...]
    path: str = ""

def normalize_environment_names(raw_names: object, *, label: str) -> tuple[str, ...]:
    if not isinstance(raw_names, (list, tuple, set, frozenset)):
        raise ValueError(f"{label} must be an array")
    normalized: set[str] = set()
    for raw_name in raw_names:
        if not isinstance(raw_name, str):
            raise ValueError(f"{label} items must be strings")
        name = str(raw_name or "").strip().upper()
        if not _ENVIRONMENT_NAME_PATTERN.fullmatch(name):
            raise ValueError(f"{label} contains invalid environment variable name")
        if name in FORBIDDEN_ENVIRONMENT_NAMES:
            raise ValueError(f"environment variable is forbidden: {name}")
        if name in normalized:
            raise ValueError(f"{label} contains duplicate environment variable: {name}")
        normalized.add(name)
    return tuple(sorted(normalized))


def compute_candidate_digest(
    candidates: tuple[str, ...],
    *,
    staging_digest: str = "",
    env_id: str = "",
    agent_type: str = "",
) -> str:
    payload = {
        "agent_type": str(agent_type or "").strip(),
        "candidates": list(candidates),
        "env_id": str(env_id or "").strip(),
        "staging_digest": str(staging_digest or "").strip(),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_selection_digest(selection: EnvironmentSelection) -> str:
    payload = {
        "candidate_digest": selection.candidate_digest,
        "selected": list(selection.selected),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def candidate_file_path(work_dir: Path, agent_version_id: str) -> Path:
    safe_version = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(agent_version_id or "").strip())
    if not safe_version:
        raise ValueError("agent_version_id must not be empty")
    return work_dir / f"environment-selection-{safe_version}.json"


def write_candidate_file(
    work_dir: Path,
    *,
    agent_version_id: str,
    candidates: tuple[str, ...],
    candidate_digest: str,
) -> Path:
    path = candidate_file_path(work_dir, agent_version_id)
    payload = {
        "version": ENVIRONMENT_SELECTION_VERSION,
        "candidate_digest": str(candidate_digest or "").strip(),
        "candidates": list(candidates),
        "selected": [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_chmod(path.parent, 0o700)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    safe_chmod(path, 0o600)
    return path


def load_environment_selection(
    path_value: str,
    *,
    expected_candidates: tuple[str, ...],
    expected_digest: str,
) -> EnvironmentSelection:
    path = Path(str(path_value or "").strip())
    if not str(path_value or "").strip():
        raise ValueError("environment selection file path must not be empty")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"environment selection file does not exist: {path}") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"failed to read environment selection file: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("environment selection file must contain an object")
    try:
        version = int(payload.get("version", 0))
    except (TypeError, ValueError):
        version = 0
    if version != ENVIRONMENT_SELECTION_VERSION:
        raise ValueError("unsupported environment selection file version")

    candidate_digest = str(payload.get("candidate_digest", "") or "").strip()
    if candidate_digest != str(expected_digest or "").strip():
        raise ValueError("environment candidates changed; regenerate the selection file")
    candidates = normalize_environment_names(payload.get("candidates"), label="candidates")
    expected = tuple(sorted(expected_candidates))
    if candidates != expected:
        raise ValueError("environment candidates changed; selection file does not match current scan")
    selected = normalize_environment_names(payload.get("selected"), label="selected")
    if not set(selected).issubset(set(expected)):
        raise ValueError("selected environment variables must be a subset of candidates")
    return EnvironmentSelection(
        candidate_digest=candidate_digest,
        candidates=candidates,
        selected=selected,
        path=str(path),
    )


def read_selected_environment_values(
    selection: EnvironmentSelection,
    *,
    process_env: Optional[Mapping[str, str]] = None,
) -> list[dict[str, str]]:
    if not selection.selected:
        return []
    source = process_env if process_env is not None else os.environ
    missing: list[str] = []
    values: list[dict[str, str]] = []
    for name in selection.selected:
        value = source.get(name)
        if not isinstance(value, str) or not value.strip():
            missing.append(name)
            continue
        values.append(
            {
                "field": name,
                "value": value,
                "use": f"Environment variable {name}",
            }
        )
    if missing:
        raise ValueError(
            "selected environment variables are missing locally: "
            + ", ".join(missing)
        )
    return values


__all__ = [
    "ENVIRONMENT_SELECTION_VERSION",
    "EnvironmentSelection",
    "FORBIDDEN_ENVIRONMENT_NAMES",
    "candidate_file_path",
    "compute_candidate_digest",
    "compute_selection_digest",
    "forbidden_environment_names_for_runtime",
    "filter_environment_names_for_runtime",
    "load_environment_selection",
    "normalize_environment_names",
    "read_selected_environment_values",
    "write_candidate_file",
]
